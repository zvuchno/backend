from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import forms

from store.constants import MONEY_DISPLAY_PRECISION


class MoneyForm(forms.ModelForm):
    """Базовая форма для денежных полей."""

    money_fields = ['price', 'price_with_donation']

    def __init__(self, *args, **kwargs) -> None:
        """Инициализирует форму и настраивает форматирование денежных полей."""
        super().__init__(*args, **kwargs)

        for field_name in self.money_fields:
            field = self.fields.get(field_name)

            if field and isinstance(field, forms.DecimalField):
                # Валидация
                field.decimal_places = MONEY_DISPLAY_PRECISION

                def format_value(
                    value,
                    precision=MONEY_DISPLAY_PRECISION,
                ) -> str:
                    if value in (None, ''):
                        return ''

                    try:
                        value = Decimal(value)
                    except InvalidOperation:
                        return str(value)
                    return f'{value:.{precision}f}'

                field.widget.format_value = format_value
                # initial округление
                value = self.initial.get(field_name) or getattr(
                    self.instance,
                    field_name,
                    None,
                )
                if isinstance(value, Decimal):
                    self.initial[field_name] = value.quantize(
                        Decimal(f'1.{"0" * MONEY_DISPLAY_PRECISION}'),
                        rounding=ROUND_HALF_UP,
                    )
