"""Утилиты для работы с денежными значениями."""

from decimal import ROUND_HALF_UP, Decimal

from store.constants import MONEY_DISPLAY_PRECISION, MONEY_ROUNDING


def format_money(value: Decimal | None) -> str:
    """Округляет и форматирует денежное значение для отображения."""
    if value is None:
        return '-'

    value = value.quantize(
        MONEY_ROUNDING,
        rounding=ROUND_HALF_UP,
    )

    return f'{value:,.{MONEY_DISPLAY_PRECISION}f}'.replace(',', ' ')


def format_document_money(value: Decimal) -> str:
    """Форматирование денег для отчетов."""
    if value is None:
        return '0,00'

    value = value.quantize(
        MONEY_ROUNDING,
        rounding=ROUND_HALF_UP,
    )

    return f'{value:,.2f}'.replace(',', ' ').replace('.', ',')
