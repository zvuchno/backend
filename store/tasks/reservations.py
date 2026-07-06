"""Celery-задачи для обслуживания резервов заказов.

Автоматически снимают истекшие резервы с заказов, у которых заполнено
поле `reserved_until`. Заказы с `reserved_until=None` считаются
бессрочно зарезервированными и не обрабатываются.
"""

import logging

from celery import shared_task
from django.db.models import Exists, OuterRef
from django.utils import timezone

from store.models import Order, Payment
from store.services import ReservationService

logger = logging.getLogger(__name__)


@shared_task
def release_expired_reservations():
    """Освобождает заказы с истекшим сроком резервирования."""
    orders = Order.objects.filter(
        status=Order.Status.RESERVED,
        reserved_until__lte=timezone.now(),
    ).annotate(
        has_pending_payment=Exists(
            Payment.objects.filter(
                order=OuterRef('pk'),
                status=Payment.PaymentStatus.PENDING,
            ),
        ),
    )

    count = 0

    for order in orders:
        if order.has_pending_payment:
            continue  # не снимаем заказы ожидающие оплату

        try:
            ReservationService.release_order_reserve(order)
            count += 1
        except Exception:
            logger.exception(
                'Ошибка снятия резерва | order_id=%s',
                order.id,
            )

    if count:
        logger.info(
            'Снятие истекших резервов завершено. Освобождено резервов: %s.',
            count,
        )
