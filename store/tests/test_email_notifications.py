"""Тесты email-уведомлений магазина."""

from decimal import Decimal
from unittest.mock import call, patch

import pytest

from store.models import Order, OrderItem, Shipment
from store.notifications import (
    send_order_paid_notifications_to_artists,
    send_shipment_registered_notification,
)
from users.tests.factories import (
    ArtistProfileFactory,
    LabelProfileFactory,
)

pytestmark = pytest.mark.django_db


def create_order() -> Order:
    """Создает заказ для проверки уведомлений."""
    return Order.objects.create(
        full_name='Иван Иванов',
        email='buyer@example.com',
        phone='+79990000000',
        status=Order.Status.PAID,
        subtotal=Decimal('1500.00'),
        total=Decimal('1500.00'),
    )


def create_order_item(
    *,
    order: Order,
    product_variant,
    shipment=None,
    name='Футболка',
) -> OrderItem:
    """Создает позицию заказа."""
    product = product_variant.product
    return OrderItem.objects.create(
        order=order,
        product_variant=product_variant,
        artist=product.artist,
        payout_recipient=product.payout_recipient,
        shipment=shipment,
        price_at_purchase=product_variant.product.price,
        unit_price=product_variant.product.price,
        quantity=1,
        product_info={
            'sku': product_variant.sku or 'sku-1',
            'kind': 'Мерч',
            'name': name,
        },
    )


@patch('store.notifications.send_telegram_notification.delay')
@patch('store.notifications.send_template_email')
def test_order_paid_email_sent_to_artist_and_label(
    mock_send_email,
    mock_send_telegram,
    variant_factory,
):
    """Письмо об оплате отправляется артисту и его лейблу."""
    label = LabelProfileFactory(
        user__email='label@example.com',
    )
    artist = ArtistProfileFactory(
        user__email='artist@example.com',
        label=label,
        telegram_chat_id=None,
    )
    product_variant = variant_factory(
        'merch',
        artist=artist,
    )
    order = create_order()
    create_order_item(
        order=order,
        product_variant=product_variant,
    )

    send_order_paid_notifications_to_artists(order)

    assert mock_send_email.call_count == 2
    mock_send_email.assert_has_calls(
        [
            call(
                subject=f'Оплачен заказ {order.order_number}',
                to_email='artist@example.com',
                template_name='order_paid',
                context={
                    'artist_name': artist.name,
                    'order_number': order.order_number,
                },
            ),
            call(
                subject=f'Оплачен заказ {order.order_number}',
                to_email='label@example.com',
                template_name='order_paid',
                context={
                    'artist_name': artist.name,
                    'order_number': order.order_number,
                },
            ),
        ],
        any_order=True,
    )
    mock_send_telegram.assert_not_called()


@patch('store.notifications.send_template_email')
def test_order_paid_email_sent_only_to_label_when_artist_has_no_account(
    mock_send_email,
    variant_factory,
):
    """При отсутствии аккаунта артиста письмо получает его лейбл."""
    label = LabelProfileFactory(
        user__email='label@example.com',
    )
    artist = ArtistProfileFactory(
        user=None,
        label=label,
    )
    product_variant = variant_factory(
        'merch',
        artist=artist,
    )
    order = create_order()
    create_order_item(
        order=order,
        product_variant=product_variant,
    )

    send_order_paid_notifications_to_artists(order)

    mock_send_email.assert_called_once_with(
        subject=f'Оплачен заказ {order.order_number}',
        to_email='label@example.com',
        template_name='order_paid',
        context={
            'artist_name': artist.name,
            'order_number': order.order_number,
        },
    )


@patch('store.notifications.send_template_email')
def test_label_receives_separate_order_email_for_each_artist(
    mock_send_email,
    variant_factory,
):
    """Лейбл получает отдельное письмо по каждому артисту заказа."""
    label = LabelProfileFactory(
        user__email='label@example.com',
    )
    first_artist = ArtistProfileFactory(
        user=None,
        label=label,
        name='Первый артист',
    )
    second_artist = ArtistProfileFactory(
        user=None,
        label=label,
        name='Второй артист',
    )
    first_variant = variant_factory(
        'merch',
        artist=first_artist,
    )
    second_variant = variant_factory(
        'merch',
        artist=second_artist,
    )
    order = create_order()
    create_order_item(
        order=order,
        product_variant=first_variant,
        name='Первый товар',
    )
    create_order_item(
        order=order,
        product_variant=second_variant,
        name='Второй товар',
    )

    send_order_paid_notifications_to_artists(order)

    assert mock_send_email.call_count == 2
    mock_send_email.assert_has_calls(
        [
            call(
                subject=f'Оплачен заказ {order.order_number}',
                to_email='label@example.com',
                template_name='order_paid',
                context={
                    'artist_name': first_artist.name,
                    'order_number': order.order_number,
                },
            ),
            call(
                subject=f'Оплачен заказ {order.order_number}',
                to_email='label@example.com',
                template_name='order_paid',
                context={
                    'artist_name': second_artist.name,
                    'order_number': order.order_number,
                },
            ),
        ],
        any_order=True,
    )


@patch('store.notifications.send_telegram_notification.delay')
@patch('store.notifications.send_template_email')
def test_shipment_email_sent_to_label_when_artist_has_no_account(
    mock_send_email,
    mock_send_telegram,
    variant_factory,
):
    """Письмо о накладной получает лейбл артиста без аккаунта."""
    label = LabelProfileFactory(
        user__email='label@example.com',
    )
    artist = ArtistProfileFactory(
        user=None,
        label=label,
        telegram_chat_id=None,
    )
    product_variant = variant_factory(
        'merch',
        artist=artist,
    )
    order = create_order()
    shipment = Shipment.objects.create(
        order=order,
        artist=artist,
        cdek_number='CDEK-123456',
    )
    create_order_item(
        order=order,
        product_variant=product_variant,
        shipment=shipment,
    )

    send_shipment_registered_notification(shipment)

    mock_send_email.assert_called_once_with(
        subject=(
            f'Сформирована накладная СДЭК для заказа {order.order_number}'
        ),
        to_email='label@example.com',
        template_name='shipment_registered',
        context={
            'artist_name': artist.name,
            'order_number': order.order_number,
            'cdek_number': 'CDEK-123456',
            'goods_list': (
                f'• {product_variant.sku or "sku-1"} | Мерч Футболка — 1 шт.'
            ),
        },
    )
    mock_send_telegram.assert_not_called()
