import logging

from store.tasks import send_telegram_notification

logger = logging.getLogger(__name__)


def send_order_paid_notifications_to_artists(order) -> None:
    """Отправляет уведомления об оплате артистам чей товар есть в заказе."""
    all_items = order.items.select_related(
        'product_variant__product__album__owner__artist_profile',
        'product_variant__product__track__album__owner__artist_profile',
        'product_variant__product__merch__owner__artist_profile',
    )

    artists = set()
    for item in all_items:
        user = item.product_variant.product.owner
        profile = getattr(user, 'artist_profile', None)
        if profile:
            artists.add(profile)

    if not artists:
        return

    for artist in artists:
        if not artist.telegram_chat_id:
            continue

        message = f'💸 *Оплачен заказ #{order.order_number}!*'

        send_telegram_notification.delay(
            artist_id=artist.id,
            message=message,
        )


def send_shipment_registered_notification(shipment) -> None:
    """Отправляет артисту уведомление о создании накладной СДЭК на доставку."""
    artist = shipment.artist

    if not artist or not artist.telegram_chat_id:
        return

    order = shipment.order
    message = (
        f'📦 *Создана накладная СДЭК!*\n\n'
        f'*Заказ:* #{order.order_number}\n'
        f'*Номер отправления:* `{shipment.tracking_number}`\n\n'
        f'Используйте этот номер для отправки посылки из вашего ПВЗ.'
    )

    send_telegram_notification.delay(
        artist_id=artist.id,
        message=message,
    )
