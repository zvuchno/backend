from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.validators import RegexValidator

from .constants import (
    MAX_AUDIOFILE_SIZE_MB,
    MAX_IMAGE_SIZE_MB,
    PROMOCODE_FORMAT_HELP_TEXT,
)


def make_file_size_validator(max_size_mb: int, optional: bool = False):
    """Фабрика валидаторов размера файла."""

    def validator(value: File | None) -> File | None:
        if optional and not value:
            return value
        try:
            filesize = value.size
        except (FileNotFoundError, OSError, AttributeError):
            raise ValidationError(
                'Файл не найден на диске. '
                'Проверьте путь к файлу или загрузите его заново.',
            )
        if filesize > max_size_mb * 1024 * 1024:
            raise ValidationError(
                f'Размер файла ({round(filesize / (1024 * 1024), 2)} MB) '
                f'превышает лимит {max_size_mb} MB.',
            )
        return value

    return validator


validate_file_size = make_file_size_validator(MAX_IMAGE_SIZE_MB, optional=True)
validate_audiofile_size = make_file_size_validator(MAX_AUDIOFILE_SIZE_MB)


def validate_price_with_donation(product, price_with_donation):
    """Проверяет корректность введенной кастомной цены.

    Если для товара разрешена переплата, проверяет, чтобы price_with_donation
    была не ниже номинальной цены продукта. Если переплата запрещена,
    проверяет, чтобы поле price_with_donation оставалось пустым.
    """
    if price_with_donation is None:
        return

    if not product.allow_overpay:
        raise ValidationError({
            'price_with_donation': 'Для этого товара переплата '
            'не предусмотрена. Пожалуйста, оставьте поле пустым.',
        })

    if price_with_donation < product.price:
        raise ValidationError({
            'price_with_donation': f'Цена с донатом не может быть ниже '
            f'номинала ({product.price:.2f} руб.)',
        })


"""Валидатор формата кода промокода."""
validate_promocode_format = RegexValidator(
    regex=r'^[A-Z0-9_-]+$',
    message=PROMOCODE_FORMAT_HELP_TEXT,
    code='invalid_promocode_format',
)
