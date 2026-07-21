import logging

from common.services import send_template_email

from store.models import OrderItem
from store.tasks import send_telegram_notification

logger = logging.getLogger(__name__)


def _get_artist_notification_emails(artist) -> set[str]:
    """Возвращает email получателей уведомлений артиста."""
    emails = set()

    if artist.user and artist.user.email:
        emails.add(artist.user.email)

    if artist.label and artist.label.user and artist.label.user.email:
        emails.add(artist.label.user.email)

    return emails


def send_order_paid_notifications_to_artists(order) -> None:
    """Отправляет уведомления об оплате артистам чей товар есть в заказе."""
    all_items = order.items.select_related(
        'product_variant__product__album__artist__user',
        'product_variant__product__album__artist__label__user',
        'product_variant__product__track__album__artist__user',
        'product_variant__product__track__album__artist__label__user',
        'product_variant__product__merch__artist__user',
        'product_variant__product__merch__artist__label__user',
    )

    artists = set()
    for item in all_items:
        artist = item.product_variant.product.artist

        if artist:
            artists.add(artist)

    if not artists:
        return

    for artist in artists:
        message = f'💸 Покупатель оплатил заказ {order.order_number}'

        if artist.telegram_chat_id:
            send_telegram_notification.delay(
                artist_id=artist.id,
                message=message,
            )

        for email in _get_artist_notification_emails(artist):
            send_template_email(
                subject=f'Оплачен заказ {order.order_number}',
                to_email=email,
                template_name='order_paid',
                context={
                    'artist_name': artist.name,
                    'order_number': order.order_number,
                },
            )


def send_shipment_registered_notification(shipment) -> None:
    """Отправляет артисту уведомление о создании накладной СДЭК на доставку."""
    artist = shipment.artist
    if not artist:
        return

    order = shipment.order

    shipment_items = OrderItem.objects.filter(shipment=shipment)
    if not shipment_items.exists():
        raise ValueError(
            f'Отправление id={shipment.id} найдено, '
            'но к нему не привязан ни один товар.',
        )

    item_lines = []
    for item in shipment_items:
        info = item.product_info or {}
        sku = info.get('sku', '—')
        kind = info.get('kind', '')
        name = info.get('name', 'Товар')
        item_lines.append(f'• {sku} | {kind} {name} — {item.quantity} шт.')

    goods_list = '\n'.join(item_lines)

    if artist.telegram_chat_id:
        message = (
            '📦 Сформирована накладная СДЭК\n\n'
            f'Заказ: {order.order_number}\n'
            f'Номер отправления: {shipment.cdek_number}\n'
            '===========================\n'
            'Товары к отправлению:\n\n'
            f'{goods_list}'
        )

        send_telegram_notification.delay(
            artist_id=artist.id,
            message=message,
        )

    for email in _get_artist_notification_emails(artist):
        send_template_email(
            subject=(
                f'Сформирована накладная СДЭК для заказа {order.order_number}'
            ),
            to_email=email,
            template_name='shipment_registered',
            context={
                'artist_name': artist.name,
                'order_number': order.order_number,
                'cdek_number': shipment.cdek_number,
                'goods_list': goods_list,
            },
        )
