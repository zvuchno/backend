import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from store.constants import STALE_ANONYMOUS_CART_DAYS
from store.models import Cart

logger = logging.getLogger(__name__)


@shared_task
def delete_stale_anonymous_carts() -> None:
    """Удаляет неактивные гостевые корзины.

    Удаляет анонимные корзины (без привязанного пользователя),
    которые не обновлялись дольше STALE_ANONYMOUS_CART_DAYS дней.
    """
    cutoff = timezone.now() - timedelta(days=STALE_ANONYMOUS_CART_DAYS)
    stale_carts = Cart.objects.filter(
        user__isnull=True,
        updated_at__lt=cutoff,
    )
    carts_count = stale_carts.count()
    stale_carts.delete()
    logger.info('Удалено брошенных гостевых корзин: %s', carts_count)
