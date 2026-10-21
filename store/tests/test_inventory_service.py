"""Тесты сервиса резервирования и списания товарных остатков."""

import threading
import time
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from store.models import Order, OrderItem
from store.services.inventory import ReservationService


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_release_skips_order_extended_while_waiting_for_lock(
    variant_factory,
    artist_user,
):
    """Не освобождает резерв, если заказ продлили до получения блокировки."""
    variant = variant_factory('merch', stock=9)
    now = timezone.now()

    order = Order.objects.create(
        user=artist_user,
        status=Order.Status.RESERVED,
        reserved_until=now - timedelta(minutes=1),
        full_name='Тестовый покупатель',
        email='buyer@example.com',
        phone='+79991234567',
    )
    OrderItem.objects.create(
        order=order,
        product_variant=variant,
        price_at_purchase=Decimal('1500'),
        unit_price=Decimal('1500'),
        quantity=1,
        artist=variant.product.merch.artist,
        payout_recipient=variant.product.merch.payout_recipient,
    )

    result = {}
    worker_started = threading.Event()

    def worker() -> None:
        close_old_connections()
        try:
            worker_started.set()
            result['released'] = (
                ReservationService.release_expired_order_reserve(order)
            )
        except Exception as exc:
            result['error'] = exc
        finally:
            connection.close()

    with transaction.atomic():
        Order.objects.select_for_update().get(pk=order.pk)

        thread = threading.Thread(target=worker)
        thread.start()

        assert worker_started.wait(timeout=5)

        # Даём фоновой задаче возможность дойти до блокировки.
        time.sleep(0.2)

        Order.objects.filter(pk=order.pk).update(
            reserved_until=timezone.now() + timedelta(minutes=15),
        )

    thread.join(timeout=5)

    assert not thread.is_alive()
    assert 'error' not in result, result.get('error')
    assert result['released'] is False

    order.refresh_from_db()
    variant.refresh_from_db()

    assert order.status == Order.Status.RESERVED
    assert order.reserved_until > timezone.now()
    assert variant.stock == 9
