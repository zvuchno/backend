from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files import File
from django.core.validators import (
    DecimalValidator,
    MinLengthValidator,
    RegexValidator,
)
from rest_framework.exceptions import ValidationError

from .constants import (
    MAX_AUDIOFILE_SIZE_MB,
    MAX_IMAGE_SIZE_MB,
    MAX_PRICE_DIGITS,
    MIN_PROMOCODE_LENGTH,
    MONEY_INTERNAL_PRECISION,
    PROMOCODE_FORMAT_HELP_TEXT,
)


class FileSizeValidator:
    """Проверяет, что размер файла не превышает заданный лимит."""

    def __init__(self, max_size_mb: int, optional: bool = False):
        """Инициализирует валидатор с заданным лимитом размера файла."""
        self.max_size_mb = max_size_mb
        self.optional = optional

    def __call__(self, value: File | None) -> File | None:
        """Проверяет размер переданного файла."""
        if self.optional and not value:
            return value

        try:
            filesize = value.size
        except (FileNotFoundError, OSError, AttributeError):
            raise DjangoValidationError(
                'Файл не найден на диске. '
                'Проверьте путь к файлу или загрузите его заново.',
            )

        if filesize > self.max_size_mb * 1024 * 1024:
            raise DjangoValidationError(
                f'Размер файла ({round(filesize / (1024 * 1024), 2)} MB) '
                f'превышает лимит {self.max_size_mb} MB.',
            )

        return value

    def deconstruct(self):
        """Возвращает параметры валидатора для миграций."""
        return (
            'store.validators.FileSizeValidator',
            (),
            {
                'max_size_mb': self.max_size_mb,
                'optional': self.optional,
            },
        )

    def __eq__(self, other):
        """Сравнивает валидаторы по настройкам."""
        return (
            isinstance(other, FileSizeValidator)
            and self.max_size_mb == other.max_size_mb
            and self.optional == other.optional
        )


validate_file_size = FileSizeValidator(
    MAX_IMAGE_SIZE_MB,
    optional=True,
)
validate_audiofile_size = FileSizeValidator(
    MAX_AUDIOFILE_SIZE_MB,
)


def validate_price_with_donation(product, price_with_donation) -> dict | None:
    """Возвращает словарь ошибок или None, если всё корректно.

    Если для товара разрешена переплата, проверяет, чтобы price_with_donation
    была не ниже номинальной цены продукта. Если переплата запрещена,
    проверяет, чтобы поле price_with_donation оставалось пустым.
    """
    if price_with_donation is None:
        return None

    if not product.allow_overpay:
        return {
            'price_with_donation': 'Для этого товара переплата '
            'не предусмотрена. Пожалуйста, оставьте поле пустым.',
        }

    if price_with_donation < product.price:
        return {
            'price_with_donation': f'Цена с донатом не может быть ниже '
            f'номинала ({product.price:.2f} руб.)',
        }

    return None


"""Валидатор формата кода промокода."""
validate_promocode_format = RegexValidator(
    regex=r'^[A-Z0-9_-]+$',
    message=PROMOCODE_FORMAT_HELP_TEXT,
    code='invalid_promocode_format',
)

"""Валидатор минимальной длины промокода."""
validate_promocode_min_length = MinLengthValidator(
    MIN_PROMOCODE_LENGTH,
    message='Код промокода должен содержать '
    f'минимум {MIN_PROMOCODE_LENGTH} символов.',
)

_price_validator = DecimalValidator(MAX_PRICE_DIGITS, MONEY_INTERNAL_PRECISION)


def validate_price(price) -> None:
    """Валидирует price на соответствие max_digits/decimal_places."""
    try:
        _price_validator(price)
    except DjangoValidationError as exc:
        raise ValidationError({'price': exc.messages}) from exc
