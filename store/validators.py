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
            f'номинала ({product.price} руб.)',
        })
