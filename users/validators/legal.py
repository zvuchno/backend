"""Валидаторы юридических и банковских данных."""

from datetime import date

from django.core.exceptions import ValidationError

from common.utils import normalize_digits

from users.constants import (
    ACCOUNT_NUMBER_MAX_LENGTH,
    BIK_MAX_LENGTH,
    INN_COMPANY_MAX_LENGTH,
    INN_PERSON_MAX_LENGTH,
    OGRN_MAX_LENGTH,
    PASSPORT_NUMBER_MAX_LENGTH,
    PASSPORT_SERIES_MAX_LENGTH,
)


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


def validate_bik(value: str) -> None:
    """Проверяет БИК банка РФ."""
    _validate_digits_number(
        value,
        BIK_MAX_LENGTH,
        'БИК',
    )


def validate_ogrn(value: str) -> None:
    """Проверяет ОГРН."""
    _validate_digits_number(
        value,
        OGRN_MAX_LENGTH,
        'ОГРН',
    )


def validate_person_inn(value: str) -> None:
    """Проверяет ИНН физического лица."""
    _validate_digits_number(
        value,
        INN_PERSON_MAX_LENGTH,
        'ИНН физического лица',
    )


def validate_company_inn(value: str) -> None:
    """Проверяет ИНН юридического лица."""
    _validate_digits_number(
        value,
        INN_COMPANY_MAX_LENGTH,
        'ИНН юридического лица',
    )


def validate_checking_account(value: str) -> None:
    """Проверяет расчетный счет."""
    _validate_digits_number(
        value,
        ACCOUNT_NUMBER_MAX_LENGTH,
        'Расчетный счет',
    )


def validate_correspondent_account(value: str) -> None:
    """Проверяет корреспондентский счет."""
    _validate_digits_number(
        value,
        ACCOUNT_NUMBER_MAX_LENGTH,
        'Корреспондентский счет',
    )


def validate_inn(value: str) -> None:
    """Проверяет ИНН физического лица или юридического лица.

    Legacy validator для старых миграций.
    """
    if not value:
        return

    normalized_value = normalize_digits(value)
    if len(normalized_value) == INN_PERSON_MAX_LENGTH:
        validate_person_inn(value)
        return
    if len(normalized_value) == INN_COMPANY_MAX_LENGTH:
        validate_company_inn(value)
        return

    raise ValidationError(
        'ИНН должен содержать 10 цифр для юридического лица '
        'или 12 цифр для физического лица.',
    )
