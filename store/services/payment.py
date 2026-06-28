"""Сервис для интеграции с ЮKassa.

Обеспечивает создание платежей, обработку вебхуков и синхронизацию
статусов платежей с заказами в системе.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from yookassa import Configuration
from yookassa import Payment as YookassaPayment

from store.models import Order, Payment

logger = logging.getLogger(__name__)

# Инициализация SDK
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def create_yookassa_payment(order):
    """Создает платеж в ЮKassa и сохраняет его запись в БД.

    Args:
        order (Order): Объект заказа.

    Returns:
        str: URL для перенаправления пользователя на страницу оплаты.

    """
    # Создаем запись в БД
    payment = Payment.objects.create(
        order=order,
        amount=order.total,
        status=Payment.PaymentStatus.PENDING,
    )

    try:
        # Формируем запрос к API
        # idempotency_key уникальный для каждой попытки
        idempotency_key = str(payment.idempotency_key)

        yookassa_res = YookassaPayment.create(
            {
                'amount': {'value': str(order.total), 'currency': 'RUB'},
                'confirmation': {
                    'type': 'redirect',
                    'return_url': settings.PAYMENT_RETURN_URL,
                },
                'capture': True,  # Автоматически подтверждать платеж
                'description': f'Заказ №{order.order_number}',
                'metadata': {'order_id': order.id},
                'receipt': {
                    'customer': {
                        'full_name': order.full_name,
                        'email': order.email,
                        'phone': order.phone,
                    },
                    # TODO: items для формирования фискального чека (54-ФЗ)
                },
            },
            idempotency_key=idempotency_key,
        )

        # Сохраняем ID платежа ЮKassa
        payment.provider_payment_id = yookassa_res.id
        payment.save()

        logger.info(
            'Платеж для заказа ID=%s успешно создан в ЮKassa. ID: %s',
            order.id,
            yookassa_res.id,
        )

        return yookassa_res.confirmation.confirmation_url

    except Exception as e:
        logger.error(
            'Ошибка при создании платежа для заказа ID=%s: %s',
            order.id,
            e,
        )
        payment.status = Payment.PaymentStatus.FAILED
        payment.save()
        raise e


def process_yookassa_webhook(notification):
    """Обрабатывает входящее уведомление (webhook) от ЮKassa.

    Функция находит соответствующий платеж в базе данных по идентификатору,
    проверяет тип события (успех или отмена) и обновляет статусы платежа
    и связанного с ним заказа.
    """
    payment_info = notification.object

    try:
        payment = Payment.objects.select_related('order').get(
            provider_payment_id=payment_info.id,
        )
    except Payment.DoesNotExist:
        logger.error(
            'Платеж %s не найден при обработке вебхука',
            payment_info.id,
        )
        return

    if notification.event == 'payment.succeeded':
        with transaction.atomic():
            # Обновляем статус платежа
            payment.status = Payment.PaymentStatus.SUCCEEDED
            payment.paid_at = timezone.now()
            payment.save()

            # Обновляем статус заказа
            payment.order.status = Order.Status.PAID
            payment.order.save()
            logger.info(
                'Платеж %s успешно оплачен для заказа %s',
                payment_info.id,
                payment.order.id,
            )

    elif notification.event == 'payment.canceled':
        with transaction.atomic():
            # Обновляем статус платежа
            payment.status = Payment.PaymentStatus.CANCELED
            if payment_info.cancellation_details:
                payment.error_code = payment_info.cancellation_details.reason
            payment.save()

            # Обновляем статус заказа
            payment.order.status = Order.Status.CANCELED
            payment.order.save()

        logger.info(
            'Платеж %s отменен для заказа %s',
            payment_info.id,
            payment.order.id,
        )
