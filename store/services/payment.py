"""Сервис для интеграции с ЮKassa.

Обеспечивает создание платежей, обработку вебхуков и синхронизацию
статусов платежей с заказами в системе.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from yookassa import Configuration
from yookassa import Payment as YookassaPayment

from store.constants import MONEY_ROUNDING
from store.exceptions import ReceiptValidationError
from store.models import Order, Payment
from store.notifications import send_order_paid_notifications_to_artists
from store.tasks import register_cdek_orders_task

logger = logging.getLogger(__name__)

# Инициализация SDK
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

RECEIPT_VAT_CODE = 1
RECEIPT_PAYMENT_MODE = 'full_prepayment'
RECEIPT_PRODUCT_SUBJECT = 'commodity'
RECEIPT_DELIVERY_SUBJECT = 'service'


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
        receipt_items = build_receipt_items(order)
        yookassa_payment = YookassaPayment.create(
            {
                'amount': {
                    'value': f'{order.total:.2f}',
                    'currency': 'RUB',
                },
                'confirmation': {
                    'type': 'embedded',
                },
                'capture': True,
                'description': f'Заказ №{order.order_number}',
                'metadata': {'order_id': order.id},
                'receipt': {
                    'customer': {
                        'full_name': order.full_name,
                        'email': order.email,
                        'phone': str(order.phone),
                    },
                    'items': receipt_items,
                },
            },
            idempotency_key=str(payment.idempotency_key),
        )
    except ReceiptValidationError:
        logger.exception(
            'Некорректные данные фискального чека для заказа id=%s.',
            order.id,
        )

        return {
            'payment_status': 'error',
            'confirmation_token': None,
        }
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

    return _handle_yookassa_payment_response(
        order=order,
        payment=payment,
        yookassa_payment=yookassa_payment,
        retry=retry,
    )


def _handle_yookassa_payment_response(
    *,
    order,
    payment,
    yookassa_payment,
    retry: bool,
) -> dict:
    """Обрабатывает ответ ЮKassa после создания платежа."""
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
    confirmation_token = getattr(confirmation, 'confirmation_token', None)

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


def build_receipt_items(order) -> list[dict]:
    """Формирует позиции фискального чека для ЮKassa."""
    receipt_items = []

    for item in order.items.all():
        line_total = item.line_total.quantize(
            MONEY_ROUNDING,
            rounding=ROUND_HALF_UP,
        )
        quantity = item.quantity

        price_per_item = (line_total / quantity).quantize(
            MONEY_ROUNDING,
            rounding=ROUND_HALF_UP,
        )

        calculated_total = price_per_item * quantity

        if calculated_total == line_total:
            receipt_items.append(
                _build_receipt_item(
                    description=_get_item_description(item),
                    quantity=quantity,
                    price=price_per_item,
                    payment_subject=RECEIPT_PRODUCT_SUBJECT,
                ),
            )
            continue

        first_quantity = quantity - 1
        first_price = price_per_item
        second_price = line_total - first_price * first_quantity

        if first_quantity:
            receipt_items.append(
                _build_receipt_item(
                    description=_get_item_description(item),
                    quantity=first_quantity,
                    price=first_price,
                    payment_subject=RECEIPT_PRODUCT_SUBJECT,
                ),
            )

        receipt_items.append(
            _build_receipt_item(
                description=_get_item_description(item),
                quantity=1,
                price=second_price,
                payment_subject=RECEIPT_PRODUCT_SUBJECT,
            ),
        )

    if order.delivery_price > 0:
        delivery_name = (
            order.delivery.get_delivery_type_display()
            if order.delivery
            else 'Доставка'
        )

        receipt_items.append(
            _build_receipt_item(
                description=delivery_name,
                quantity=1,
                price=order.delivery_price,
                payment_subject=RECEIPT_DELIVERY_SUBJECT,
            ),
        )

    receipt_total = sum(
        Decimal(receipt_item['amount']['value']) * receipt_item['quantity']
        for receipt_item in receipt_items
    ).quantize(
        MONEY_ROUNDING,
        rounding=ROUND_HALF_UP,
    )

    order_total = order.total.quantize(
        MONEY_ROUNDING,
        rounding=ROUND_HALF_UP,
    )

    if receipt_total != order_total:
        raise ReceiptValidationError(
            'Сумма позиций чека не совпадает с суммой заказа: '
            f'{receipt_total} != {order_total}.',
        )

    return receipt_items


def _build_receipt_item(
    *,
    description,
    quantity,
    price,
    payment_subject,
) -> dict:
    """Формирует одну позицию фискального чека."""
    return {
        'description': description[:128],
        'quantity': quantity,
        'amount': {
            'value': f'{price:.2f}',
            'currency': 'RUB',
        },
        'vat_code': RECEIPT_VAT_CODE,
        'payment_subject': payment_subject,
        'payment_mode': RECEIPT_PAYMENT_MODE,
    }


def _get_item_description(order_item) -> str:
    """Возвращает название товара для фискального чека."""
    product_info = order_item.product_info

    description = ' '.join(
        filter(
            None,
            (
                product_info.get('kind'),
                product_info.get('name'),
            ),
        ),
    )
    return description or f'Товар #{order_item.product_variant_id}'


def mark_payment_succeeded(payment):
    """Отмечает платеж как успешно оплаченный и отправляет уведомления."""
    with transaction.atomic():
        payment.status = Payment.PaymentStatus.SUCCEEDED
        payment.paid_at = timezone.now()
        payment.save(update_fields=['status', 'paid_at', 'updated_at'])

        payment.order.status = Order.Status.PAID
        payment.order.reserved_until = None
        payment.order.save(
            update_fields=['status', 'reserved_until', 'updated_at'],
        )

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
