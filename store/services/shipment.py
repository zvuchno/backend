"""Обработка статусов отправлений СДЭК (вебхуки)."""

import logging
from datetime import datetime
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from store.models import Order, Shipment, ShipmentStatusEvent

logger = logging.getLogger(__name__)

DS = Shipment.DeliveryStatus

# Посылка уже у перевозчика / в пути
SHIPPED_STATUSES = frozenset(
    {
        DS.TAKEN_BY_TRANSPORTER_FROM_SENDER_CITY,
        DS.SENT_TO_RECIPIENT_CITY,
        DS.ACCEPTED_IN_RECIPIENT_CITY,
        DS.ACCEPTED_AT_TRANSIT_WAREHOUSE,
        DS.READY_FOR_SHIPMENT_IN_TRANSIT_CITY,
        DS.TAKEN_BY_TRANSPORTER_FROM_TRANSIT_CITY,
        DS.ACCEPTED_AT_RECIPIENT_CITY_WAREHOUSE,
        DS.ENTERED_TO_RECIPIENT_CITY_WAREHOUSE,
        DS.ACCEPTED_AT_PICK_UP_POINT,
        DS.ENTERED_TO_PICK_UP_POINT,
        DS.POSTOMAT_POSTED,
        DS.TAKEN_BY_COURIER,
    },
)

DELIVERED_STATUSES = frozenset({DS.DELIVERED, DS.POSTOMAT_RECEIVED})

# Не мешают завершить заказ, когда остальные посылки вручены
NON_BLOCKING_FOR_COMPLETION = DELIVERED_STATUSES | {DS.REMOVED}

# Пока только логируем
PROBLEM_STATUSES = frozenset(
    {
        DS.NOT_DELIVERED,
        DS.INVALID,
        DS.SENT_TO_SENDER_CITY,
        DS.RETURNED_TO_SENDER_CITY_WAREHOUSE,
        DS.RETURNED_TO_TRANSIT_WAREHOUSE,
        DS.RETURNED_TO_RECIPIENT_CITY_WAREHOUSE,
    },
)

RESULT_NOT_FOUND = 'not_found'
RESULT_DUPLICATE = 'duplicate'
RESULT_STALE = 'stale'
RESULT_APPLIED = 'applied'


def parse_event_time(value) -> datetime:
    """Парсит время события СДЭК; при неудаче возвращает «сейчас»."""
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        return timezone.now()
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


@transaction.atomic
def apply_status_event(
    *,
    cdek_uuid: str,
    status_code: str,
    occurred_at: datetime,
    cdek_number: str = '',
    raw: dict | None = None,
) -> str:
    """Идемпотентно применяет событие статуса к отправлению.

    Порядок блокировок везде одинаковый: сначала заказ, потом отправление.
    """
    row = (
        Shipment.objects
        .filter(cdek_uuid=cdek_uuid)
        .values_list('pk', 'order_id')
        .first()
    )
    if row is None:
        logger.warning(
            'СДЭК: отправление не найдено, uuid=%s, status=%s',
            cdek_uuid,
            status_code,
        )
        return RESULT_NOT_FOUND

    shipment_pk, order_id = row
    Order.objects.select_for_update().get(pk=order_id)
    shipment = Shipment.objects.select_for_update().get(pk=shipment_pk)

    _, created = ShipmentStatusEvent.objects.get_or_create(
        shipment=shipment,
        code=status_code,
        occurred_at=occurred_at,
        defaults={'raw': raw or {}},
    )
    if not created:
        return RESULT_DUPLICATE

    is_latest = _update_shipment_status(
        shipment,
        status_code,
        occurred_at,
    )
    _update_cdek_number(shipment, cdek_number)

    if is_latest and status_code in PROBLEM_STATUSES:
        logger.warning(
            'СДЭК: проблемный статус отправления: shipment_id=%s, '
            'order_id=%s, status=%s',
            shipment.pk,
            order_id,
            status_code,
        )

    sync_order_status(shipment)
    return RESULT_APPLIED if is_latest else RESULT_STALE


def _update_shipment_status(
    shipment: Shipment,
    status_code: str,
    occurred_at: datetime,
) -> bool:
    """Обновляет статус отправления, если событие актуальнее."""
    changed_at = shipment.delivery_status_changed_at
    is_latest = changed_at is None or occurred_at >= changed_at

    if not is_latest:
        return False

    update_fields = []

    if shipment.delivery_status != status_code:
        shipment.delivery_status = status_code
        update_fields.append('delivery_status')

    if changed_at != occurred_at:
        shipment.delivery_status_changed_at = occurred_at
        update_fields.append('delivery_status_changed_at')

    if update_fields:
        update_fields.append('updated_at')
        shipment.save(update_fields=update_fields)

    return True


def _update_cdek_number(shipment: Shipment, cdek_number: str) -> None:
    """Сохраняет номер отправления СДЭК."""
    if not cdek_number:
        return

    if not shipment.cdek_number:
        shipment.cdek_number = cdek_number
        shipment.save(update_fields=['cdek_number', 'updated_at'])
    elif shipment.cdek_number != cdek_number:
        logger.warning(
            'Номер заказа СДЭК не совпадает: shipment_id=%s, '
            'saved_cdek_number=%s, webhook_cdek_number=%s',
            shipment.pk,
            shipment.cdek_number,
            cdek_number,
        )


@transaction.atomic
def sync_order_status(shipment: Shipment) -> None:
    """Обновляет статус заказа по статусам отправлений."""
    order = Order.objects.select_for_update().get(pk=shipment.order_id)

    if order.status in {Order.Status.COMPLETED, Order.Status.CANCELED}:
        return

    status = shipment.delivery_status

    if order.status == Order.Status.PAID and status in SHIPPED_STATUSES:
        order.status = Order.Status.SHIPPED
        order.save(update_fields=['status', 'updated_at'])
        return

    if status not in DELIVERED_STATUSES:
        return

    if order.shipments.exclude(
        delivery_status__in=NON_BLOCKING_FOR_COMPLETION,
    ).exists():
        return

    order.status = Order.Status.COMPLETED
    order.save(update_fields=['status', 'updated_at'])
