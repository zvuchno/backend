import logging

from store.models import Order
from store.services import ReservationService

logger = logging.getLogger(__name__)

Status = Order.Status

# Статусы, при которых товар должен быть зарезервирован
RESERVED_GROUP = {
    Status.RESERVED,
    Status.PAID,
    Status.SHIPPED,
    Status.COMPLETED,
}

# Статусы, при которых резерва быть не должно
UNRESERVED_GROUP = {
    Status.CREATED,
    Status.CANCELED,
}


def handle_order_status_change(order: Order, old_status: str) -> None:
    """Обрабатывает изменение статуса заказа из админки."""
    new_status = order.status
    if old_status == new_status:
        return

    logger.info(
        'Изменение статуса заказа | order_id=%s | %s → %s',
        order.id,
        old_status,
        new_status,
    )

    was_reserved = old_status in RESERVED_GROUP
    is_reserved = new_status in RESERVED_GROUP

    if not was_reserved and is_reserved:
        ReservationService.reserve_order(order, status=new_status)
    elif was_reserved and not is_reserved:
        ReservationService.release_order_reserve(order, status=new_status)
