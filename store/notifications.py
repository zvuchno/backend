import logging
from collections import defaultdict
from datetime import date

from django.core.exceptions import ObjectDoesNotExist

from common.services import send_template_email

from store.models import Delivery
from store.tasks import send_telegram_notification
from store.telegram_messages import (
    format_cdek_notification,
    format_digital_notification,
    format_pickup_notification,
)

logger = logging.getLogger(__name__)

CUSTOMER_NAME_LIMIT = 50
CONTACT_LIMIT = 100
ITEM_TITLE_LIMIT = 100


# --- Подготовка данных для Telegram ---


def _short(text: str | None, limit: int) -> str:
    """Схлопывает пробелы и переводы строк, обрезает по лимиту."""
    text = ' '.join((text or '').split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + '…'


def _item_title(item) -> str:
    info = item.product_info or {}
    name = info.get('name', 'Товар')
    variant = info.get('variant_name')
    sku = _short(info.get('sku'), 50)

    title = f'{name} ({variant})' if variant else name
    title = _short(title, ITEM_TITLE_LIMIT)
    return f'{title} [{sku}]' if sku else title


def _split_items(items) -> tuple[list, list]:
    physical = [i for i in items if not i.product_variant.is_digital]
    digital = [i for i in items if i.product_variant.is_digital]
    return physical, digital


def _physical_pairs(items) -> list[tuple[str, int]]:
    return [(_item_title(i), i.quantity) for i in items]


def _digital_titles(items) -> list[str]:
    return list(dict.fromkeys(_item_title(i) for i in items))


def _join_comments(items) -> str:
    comments = (i.comment.strip() for i in items)
    return ' / '.join(dict.fromkeys(c for c in comments if c))


def _is_pickup(order) -> bool:
    delivery = order.delivery
    return (
        delivery is not None
        and delivery.delivery_type == Delivery.DeliveryType.ARTIST_PICKUP
    )


def _pickup_date(point: dict) -> str | None:
    raw = point.get('date')
    if not raw:
        return None
    try:
        return date.fromisoformat(raw).strftime('%d.%m.%Y')
    except ValueError:
        return raw


def _get_dropoff_address(artist) -> str:
    """Возвращает адрес точки, куда артист относит посылку."""
    try:
        city = artist.shipping_point.city
        address = artist.shipping_point.address
    except ObjectDoesNotExist:
        logger.warning(
            'У артиста id=%s нет точки отправки СДЭК.',
            artist.id,
        )
        return ''
    return ', '.join(part for part in (city, address) if part)


def _build_new_order_message(order, items) -> str | None:
    """Формирует уведомление артисту о новом заказе.

    Возвращает текст, если у артиста только цифровые товары или заказ
    на самовывоз. Для доставки СДЭК возвращает None: уведомление уйдёт
    позже, когда отправление будет зарегистрировано.
    """
    physical, digital = _split_items(items)
    comment = _join_comments(items)

    if not physical:
        return format_digital_notification(
            order,
            _digital_titles(digital),
            comment,
        )

    if _is_pickup(order):
        point = order.pickup_point or {}
        return format_pickup_notification(
            order,
            pickup_address=point.get('address'),
            physical_items=_physical_pairs(physical),
            digital_releases=_digital_titles(digital),
            customer_info=_short(order.full_name, CUSTOMER_NAME_LIMIT),
            pickup_contact=_short(order.pickup_contact, CONTACT_LIMIT),
            event_date=_pickup_date(point),
            comment=comment,
        )
    return None


def _build_cdek_message(order, shipment, artist_items) -> str:
    """Формирует уведомление артисту о зарегистрированном отправлении СДЭК.

    В список к отправке попадают только физические товары этого
    отправления. Цифровые релизы и комментарии покупателя берутся
    из всех позиций артиста в заказе.
    """
    physical, digital = _split_items(artist_items)
    shipment_items = [i for i in physical if i.shipment_id == shipment.id]

    return format_cdek_notification(
        order,
        shipment,
        physical_items=_physical_pairs(shipment_items),
        digital_releases=_digital_titles(digital),
        dropoff_address=_get_dropoff_address(shipment.artist),
        comment=_join_comments(artist_items),
    )


def _send_telegram(artist, message: str) -> None:
    if artist.telegram_chat_id:
        send_telegram_notification.delay(
            artist_id=artist.id,
            message=message,
        )


# --- Email ---


def _get_artist_notification_emails(artist) -> set[str]:
    """Возвращает email получателей уведомлений артиста."""
    emails = set()
    if artist.user and artist.user.email:
        emails.add(artist.user.email)
    if artist.label and artist.label.user and artist.label.user.email:
        emails.add(artist.label.user.email)
    return emails


def _get_order_paid_emails(artist, items) -> set[str]:
    """Возвращает email артиста и получателей выплат по его позициям."""
    emails = {item.payout_recipient.email for item in items}
    if artist.user:
        emails.add(artist.user.email)
    return {email for email in emails if email}


def _send_email(email: str, *, subject, template_name, context) -> None:
    """Отправляет письмо, не прерывая рассылку при ошибке."""
    try:
        send_template_email(
            subject=subject,
            to_email=email,
            template_name=template_name,
            context=context,
        )
    except Exception:
        logger.exception(
            'Не удалось отправить письмо %s на %s',
            template_name,
            email,
        )


def _send_order_paid_emails(order, artist, items) -> None:
    for email in _get_order_paid_emails(artist, items):
        _send_email(
            email,
            subject=f'Оплачен заказ {order.order_number}',
            template_name='order_paid',
            context={
                'artist_name': artist.name,
                'order_number': order.order_number,
            },
        )


def _send_shipment_registered_emails(order, artist, shipment, items) -> None:
    goods_list = '\n'.join(
        '• {} | {} — {} шт.'.format(
            (item.product_info or {}).get('sku', '—'),
            (item.product_info or {}).get('name', 'Товар'),
            item.quantity,
        )
        for item in items
    )
    for email in _get_artist_notification_emails(artist):
        _send_email(
            email,
            subject=(
                f'Сформирована накладная СДЭК для заказа {order.order_number}'
            ),
            template_name='shipment_registered',
            context={
                'artist_name': artist.name,
                'order_number': order.order_number,
                'cdek_number': shipment.cdek_number,
                'goods_list': goods_list,
            },
        )


# --- События ---


def notify_artists_about_new_order(order) -> None:
    """Уведомляет артистов о новом заказе после его оплаты.

    Письмо получают все артисты заказа. Сообщение в Telegram уходит
    сразу только тем, у кого цифровые товары или самовывоз. Артисту
    с доставкой СДЭК оно отправляется позже, когда отправление
    будет зарегистрировано.
    """
    items = order.items.select_related(
        'artist__user',
        'payout_recipient',
        'product_variant',
    )
    items_by_artist = defaultdict(list)
    for item in items:
        items_by_artist[item.artist].append(item)

    for artist, artist_items in items_by_artist.items():
        try:
            message = _build_new_order_message(order, artist_items)
        except Exception:
            logger.exception(
                'Не удалось собрать Telegram-сообщение (заказ %s, артист %s)',
                order.order_number,
                artist.id,
            )
            message = None

        if message:
            _send_telegram(artist, message)
        _send_order_paid_emails(order, artist, artist_items)


def notify_artist_about_cdek_order(shipment) -> None:
    """Уведомляет артиста о новом заказе с доставкой СДЭК.

    Вызывается после регистрации отправления, когда известны номер
    и ссылка на трекинг. В Telegram уходит полное уведомление: товары
    к отправке, цифровые релизы, комментарий покупателя, ПВЗ и срок.
    """
    artist = shipment.artist
    if not artist:
        return
    order = shipment.order

    artist_items = list(
        order.items.filter(artist=artist).select_related('product_variant'),
    )
    shipment_items = [i for i in artist_items if i.shipment_id == shipment.id]
    if not shipment_items:
        raise ValueError(
            f'Отправление id={shipment.id} найдено, '
            'но к нему не привязан ни один товар.',
        )

    try:
        message = _build_cdek_message(order, shipment, artist_items)
    except Exception:
        logger.exception(
            'Не удалось собрать Telegram-сообщение (отправление %s)',
            shipment.id,
        )
    else:
        _send_telegram(artist, message)

    _send_shipment_registered_emails(order, artist, shipment, shipment_items)
