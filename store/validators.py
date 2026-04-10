from django.core.exceptions import ValidationError

from .constants import MAX_IMAGE_SIZE_MB


def validate_file_size(value):
    """Ограничения размера обложки до 10 MB."""
    filesize = value.size

    if filesize > MAX_IMAGE_SIZE_MB * 1024 * 1024:  # MB в байтах
        raise ValidationError(
            f'Размер файла не должен превышать {MAX_IMAGE_SIZE_MB} MB',
        )
    return value


def validate_custom_price(product, custom_price):
    """Проверяет корректность введенной кастомной цены.

    Если для товара разрешена переплата, проверяет, чтобы custom_price
    была не ниже номинальной цены продукта. Если переплата запрещена,
    проверяет, чтобы поле custom_price оставалось пустым.
    """
    if custom_price is None:
        return

    if not product.allow_overpay:
        raise ValidationError({
            'custom_price': 'Для этого товара переплата '
            'не предусмотрена. Пожалуйста, оставьте поле пустым.',
        })

    if custom_price < product.price:
        raise ValidationError({
            'custom_price': f'Цена с донатом не может быть ниже '
            f'номинала ({product.price} руб.)',
        })
