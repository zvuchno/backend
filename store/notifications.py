import logging

from store.models import OrderItem
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

        message = f'💸 Покупатель оплатил заказ {order.order_number}'

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

    shipment_items = OrderItem.objects.filter(shipment=shipment)

    item_lines = []
    for item in shipment_items:
        info = item.product_info or {}
        sku = info.get('sku', '—')
        kind = info.get('kind', '')
        name = info.get('name', 'Товар')
        item_lines.append(f'• {sku} | {kind} {name} — x{item.quantity} шт.')

    goods_list = '\n'.join(item_lines)

    message = (
        '📦 Сформирована накладная СДЭК\n\n'
        f'Заказ: {order.order_number}\n'
        f'Номер отправления: `{shipment.cdek_number}`\n'
        '================================\n'
        'Товары к отправлению:\n'
        f'{goods_list}'
    )

    send_telegram_notification.delay(
        artist_id=artist.id,
        message=message,
    )
