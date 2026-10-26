from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from common.utils import format_document_money

from store.constants import (
    CDEK_HANDOFF_DEADLINE_DAYS,
    CDEK_TRACKING_URL,
)


# ======================================================
# ЗАКАЗЫ
# ======================================================
def _append_physical_items(
    lines: list[str],
    physical_items: list[tuple[str, int]],
) -> None:
    """Добавляет список физических товаров."""
    if not physical_items:
        return

    lines.extend([
        '',
        '🧺 Подготовить:',
        *(f'• {name} — {quantity} шт.' for name, quantity in physical_items),
    ])


def _append_digital_releases(
    lines: list[str],
    digital_releases: list[str],
) -> None:
    """Добавляет список цифровых релизов."""
    if not digital_releases:
        return

    lines.extend([
        '',
        '🎧 Цифровое:',
        *(f'• {title}' for title in digital_releases),
        '(Уже доступно фанату в Библиотеке)',
    ])


def _append_customer_comment(lines: list[str], comment: str | None) -> None:
    """Добавляет комментарий покупателя, если он указан."""
    comment = ' '.join((comment or '').split())[:1000]
    if not comment:
        return
    lines.extend(['', '💬 Сообщение от покупателя:', comment])


def _format_cdek_deadline() -> str:
    """Формирует дату передачи заказа в СДЭК."""
    deadline = timezone.now() + timedelta(days=CDEK_HANDOFF_DEADLINE_DAYS)
    return timezone.localtime(deadline).strftime('%d.%m.%Y')


def format_digital_notification(
    order,
    digital_releases: list[str],
    comment: str = '',
) -> str:
    """Формирует уведомление о покупке цифрового релиза."""
    lines = [
        '🎵 Покупка: цифровой релиз',
        '',
        f'🧾 Заказ №{order.order_number}',
    ]

    _append_digital_releases(lines, digital_releases)
    _append_customer_comment(lines, comment)

    return '\n'.join(lines)


def format_cdek_notification(
    order,
    shipment,
    physical_items: list[tuple[str, int]],
    digital_releases: list[str],
    dropoff_address: str,
    comment: str = '',
) -> str:
    """Формирует уведомление о заказе с доставкой СДЭК."""
    tracking_url = CDEK_TRACKING_URL.format(
        cdek_number=shipment.cdek_number,
    )
    lines = [
        '📦 Заказ с доставкой: нужно отправить',
        '',
        f'🧾 Заказ №{order.order_number}',
    ]

    _append_physical_items(lines, physical_items)
    _append_digital_releases(lines, digital_releases)

    lines.extend([
        '',
        '📍 Отнести в ПВЗ СДЭК:',
        dropoff_address or '—',
        f'⏳ Срок: до {_format_cdek_deadline()}',
        f'📦 Номер отправления: {shipment.cdek_number}',
        f'🔗 Отследить: {tracking_url}',
    ])

    _append_customer_comment(lines, comment)

    return '\n'.join(lines)


def format_pickup_notification(
    order,
    pickup_address: str | None,
    physical_items: list[tuple[str, int]],
    digital_releases: list[str],
    customer_info: str | None = None,
    pickup_contact: str | None = None,
    event_date: str | None = None,
    comment: str = '',
) -> str:
    """Формирует уведомление о заказе с самовывозом."""
    lines = [
        '🤝 Самовывоз: нужно передать',
        '',
        f'🧾 Заказ №{order.order_number}',
    ]

    customer = ' · '.join(
        part for part in (customer_info, pickup_contact) if part
    )
    if customer:
        lines.append(f'👤 {customer}')

    _append_physical_items(lines, physical_items)
    _append_digital_releases(lines, digital_releases)

    lines.extend([
        '',
        '📍 Адрес самовывоза:',
        pickup_address or '—',
    ])

    if event_date:
        lines.append(f'Дата: {event_date}')

    lines.extend([
        '',
        'Передай заказ лично. Связаться с покупателем и найти его '
        'в списке можно по контакту.',
        'Лучше написать ему не откладывая: фанат уже ждёт 🙂',
    ])

    _append_customer_comment(lines, comment)

    return '\n'.join(lines)


# ======================================================
# ОТЧЕТЫ
# ======================================================


MONTHS_NOMINATIVE = (
    'январь',
    'февраль',
    'март',
    'апрель',
    'май',
    'июнь',
    'июль',
    'август',
    'сентябрь',
    'октябрь',
    'ноябрь',
    'декабрь',
)
MONTHS_GENITIVE = (
    'января',
    'февраля',
    'марта',
    'апреля',
    'мая',
    'июня',
    'июля',
    'августа',
    'сентября',
    'октября',
    'ноября',
    'декабря',
)


def format_monthly_report_notification(
    period_start: date,
    period_end: date,
    items_sold: int,
    revenue: Decimal,
    payout: Decimal,
    report_url: str,
    with_pdf: bool = False,
) -> str:
    """Формирует уведомление артисту о готовом месячном отчёте."""
    payout_month = period_end + timedelta(days=1)

    lines = [
        f'📊 Отчёт за {MONTHS_NOMINATIVE[period_start.month - 1]} готов',
        '',
        f'Период: {period_start:%d.%m.%Y} – {period_end:%d.%m.%Y}',
        f'Продано: {items_sold} шт. на {format_document_money(revenue)} ₽',
        f'К выплате: {format_document_money(payout)} ₽',
        '',
        f'Полный отчёт в личном кабинете: {report_url}',
    ]
    if with_pdf:
        lines.append('(PDF приложен к сообщению)')

    lines.extend([
        '',
        f'Выплата будет до 10 {MONTHS_GENITIVE[payout_month.month - 1]}.',
        'Отчёт считается принятым, если в течение 3 дней '
        'ты не сообщишь о замечаниях.',
    ])

    return '\n'.join(lines)
