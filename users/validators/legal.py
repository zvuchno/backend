"""Валидаторы юридических и банковских данных."""

from datetime import date

from django.core.exceptions import ValidationError

from users.constants import (
    PASSPORT_NUMBER_MAX_LENGTH,
    PASSPORT_SERIES_MAX_LENGTH,
)


def normalize_digits(value: str) -> str:
    """Нормализация числового поля."""
    return ''.join(d for d in str(value) if d.isdigit())


def _validate_digits_number(
    value: str,
    length: int,
    field_name: str,
) -> None:
    """Проверяет, что поле содержит заданное количество цифр."""
    if not value:
        return
    normalized_value = normalize_digits(value)
    if not normalized_value:
        raise ValidationError(
            f'{field_name} должно содержать только цифры.',
        )
    if len(normalized_value) != length:
        raise ValidationError(
            f'{field_name} должно содержать {length} цифр.',
        )


def _validate_not_future_or_distant_past_date(
    value: date,
    field_name: str,
) -> None:
    """Дата не из будущего и не из далекого прошлого."""
    if not value:
        return
    today = date.today()
    if value > today:
        raise ValidationError(
            f'{field_name} не может быть из будущего.',
        )
    if value.year < 1900:
        raise ValidationError(
            f'{field_name} не может быть так далеко в прошлом.',
        )


def validate_passport_series(value: str) -> None:
    """Проверяет серию паспорта РФ."""
    _validate_digits_number(
        value,
        PASSPORT_SERIES_MAX_LENGTH,
        'Серия паспорта',
    )


def validate_passport_number(value: str) -> None:
    """Проверяет номер паспорта РФ."""
    _validate_digits_number(
        value,
        PASSPORT_NUMBER_MAX_LENGTH,
        'Номер паспорта',
    )


def validate_birth_date(value: date) -> None:
    """Проверяет дату рождения."""
    _validate_not_future_or_distant_past_date(
        value,
        'Дата рождения',
    )


def validate_passport_issue_date(value: date) -> None:
    """Проверяет дату выдачи паспорта."""
    _validate_not_future_or_distant_past_date(
        value,
        'Дата выдачи паспорта',
    )
