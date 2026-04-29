"""Утилиты для работы с денежными значениями."""

from decimal import ROUND_HALF_UP, Decimal


def format_money(value: Decimal, places: str = '0.01') -> str:
    """Округление и форматирование денег для UI."""
    if value is None:
        return '-'

    value = value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    return f'{value:,.2f}'.replace(',', ' ')
