"""Утилиты для работы с денежными значениями."""

from decimal import ROUND_HALF_UP, Decimal

from store.constants import MONEY_ROUNDING


def format_money(value: Decimal, places: str = '0.01') -> str:
    """Округление и форматирование денег для UI."""
    if value is None:
        return '-'

    value = value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    return f'{value:,.2f}'.replace(',', ' ')


def format_document_money(value: Decimal) -> str:
    """Форматирование денег для отчетов."""
    if value is None:
        return '0,00'

    value = value.quantize(
        MONEY_ROUNDING,
        rounding=ROUND_HALF_UP,
    )

    return f'{value:,.2f}'.replace(',', ' ').replace('.', ',')
