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
from store.notifications import send_order_paid_notifications_to_artists
from store.tasks import register_cdek_orders_task

logger = logging.getLogger(__name__)

# Инициализация SDK
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def create_yookassa_payment(order, retry=True):
    """Создает или переиспользует платеж в ЮKassa."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.status == Order.Status.CREATED:
            logger.info(
                'Платёж заблокирован: заказ не зарезервирован | order_id=%s',
                order.id,
            )
            return {
                'status': 'not_reserved',
                'confirmation_token': None,
            }

        if order.status == Order.Status.PAID:
            logger.info(
                'Попытка инициировать оплату уже '
                'оплаченного заказа: order_id=%s',
                order.id,
            )
            return {
                'status': 'already_paid',
                'confirmation_token': None,
            }

        if order.status != Order.Status.RESERVED:
            logger.warning(
                'Попытка оплаты заказа в некорректном статусе '
                '| order_id=%s | status=%s',
                order.id,
                order.status,
            )
            return {
                'status': 'invalid_state',
                'confirmation_token': None,
            }

        payment, created = Payment.objects.get_or_create(
            order=order,
            status=Payment.PaymentStatus.PENDING,
            defaults={
                'amount': order.total,
            },
        )

    if created:
        logger.info(
            'Создан новый pending-платеж id=%s для заказа id=%s.',
            payment.id,
            order.id,
        )
    else:
        logger.info(
            'Переиспользуется pending-платеж id=%s для заказа id=%s.',
            payment.id,
            order.id,
        )

    try:
        # Формируем запрос к API
        yookassa_payment = YookassaPayment.create(
            {
                'amount': {
                    'value': str(order.total),
                    'currency': 'RUB',
                },
                'confirmation': {
                    'type': 'redirect',
                    'return_url': 'https://dev.zvuchno.space/order/order-succeed',
                },
                'capture': True,
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
            idempotency_key=str(payment.idempotency_key),
        )
    except Exception:
        logger.exception(
            'Ошибка создания платежа ЮKassa для заказа id=%s.',
            order.id,
        )

        return {
            'payment_status': 'error',
            'confirmation_token': None,
        }

    payment.provider_payment_id = yookassa_payment.id
    payment.save(update_fields=['provider_payment_id', 'updated_at'])

    if yookassa_payment.status == 'succeeded':
        logger.info(
            'Платеж для order_id=%s уже имеет статус succeeded '
            'в ЮKassa, обновляем локальные статусы.',
            order.id,
        )
        mark_payment_succeeded(payment)
        return {
            'payment_status': 'succeeded',
            'confirmation_token': None,
        }

    if yookassa_payment.status == 'canceled':
        payment.status = Payment.PaymentStatus.CANCELED

        details = getattr(yookassa_payment, 'cancellation_details', None)
        reason = getattr(details, 'reason', 'неизвестная причина')
        payment.error_code = reason
        payment.save(update_fields=['status', 'error_code', 'updated_at'])

        logger.warning(
            'Платеж отменен: внутренний ID=%s, ID в ЮKassa=%s, причина=%s',
            payment.id,
            yookassa_payment.id,
            reason,
        )
        if retry:
            logger.info(
                'Создаем новую попытку оплаты для order_id=%s '
                'после отмены предыдущего платежа.',
                order.id,
            )
            return create_yookassa_payment(order, retry=False)
        return {'payment_status': 'canceled', 'confirmation_token': None}

    confirmation = getattr(yookassa_payment, 'confirmation', None)
    confirmation_token = getattr(confirmation, 'confirmation_url', None)

    if not confirmation_token:
        logger.error(
            'ЮKassa не вернула confirmation_token | order_id=%s '
            '| payment_id=%s | status=%s',
            order.id,
            yookassa_payment.id,
            yookassa_payment.status,
        )
        return {
            'payment_status': 'error',
            'confirmation_token': None,
        }
    return {
        'payment_status': 'pending',
        'confirmation_token': confirmation_token,
    }


def mark_payment_succeeded(payment):
    """Отмечает платеж как успешно оплаченный и отправляет уведомления."""
    with transaction.atomic():
        payment.status = Payment.PaymentStatus.SUCCEEDED
        payment.paid_at = timezone.now()
        payment.save(update_fields=['status', 'paid_at', 'updated_at'])

        payment.order.status = Order.Status.PAID
        payment.order.save(update_fields=['status', 'updated_at'])

        transaction.on_commit(
            lambda: (
                # Отправлем уведомление артистам
                send_order_paid_notifications_to_artists(payment.order),
                # Регистрируем заказ в СДЭК
                register_cdek_orders_task.delay(payment.order_id),
            ),
        )

    logger.info(
        'Платеж %s успешно обработан. Заказ id=%s оплачен.',
        payment.provider_payment_id,
        payment.order.id,
    )


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
            'Платеж с provider_payment_id=%s не найден.',
            payment_info.id,
        )
        return

    if notification.event == 'payment.succeeded':
        if payment.status == Payment.PaymentStatus.SUCCEEDED:
            logger.info(
                'Webhook для платежа %s уже был обработан.',
                payment.provider_payment_id,
            )
            return

        mark_payment_succeeded(payment)

    elif notification.event == 'payment.canceled':
        if payment.status == Payment.PaymentStatus.CANCELED:
            logger.info(
                'Webhook отмены платежа %s уже был обработан.',
                payment.provider_payment_id,
            )
            return

        with transaction.atomic():
            payment.status = Payment.PaymentStatus.CANCELED

            reason = None
            if payment_info.cancellation_details:
                reason = payment_info.cancellation_details.reason
                payment.error_code = reason

            payment.save(update_fields=['status', 'error_code', 'updated_at'])

        logger.info(
            'Платеж %s по заказу id=%s отменен. Причина: %s',
            payment.provider_payment_id,
            payment.order.id,
            reason or 'неизвестная причина',
        )

    else:
        logger.warning(
            'Webhook получено необрабатываемое событие: %s',
            notification.event,
        )
