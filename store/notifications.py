import logging

from store.tasks import send_telegram_notification

logger = logging.getLogger(__name__)


def send_order_paid_notifications_to_artists(order) -> None:
    """Отправляет уведомления об оплате артистам чей товар есть в заказе."""
    all_items = order.items.select_related(
        'product_variant__product__album__artist',
        'product_variant__product__track__album__artist',
        'product_variant__product__merch__artist',
    )

    artists = set()
    for item in all_items:
        artist = item.product_variant.product.artist

        if artist:
            artists.add(artist)

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
        f'Заказ: #{order.order_number}\n\n'
        f'Номер отправления: {shipment.tracking_number}\n'
        f'(используйте этот номер для отправки посылки из вашего ПВЗ)'
    )

    send_telegram_notification.delay(
        artist_id=artist.id,
        message=message,
    )
