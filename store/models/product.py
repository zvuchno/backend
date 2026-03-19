from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

from store.constants import (
    MAX_PRICE_DIGITS,
    MAX_STR_LENGTH,
    PRICE_DECIMAL_PLACES,
)

User = get_user_model()


class Product(models.Model):
    """Это универсальная карточка товара."""

    base_price = models.DecimalField(
        'Цена',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Цена, руб.',
    )
    allow_fans_overpay = models.BooleanField(
        'Разрешить платить больше',
        default=False,
        help_text='Если включено, фанаты смогут заплатить больше стоимости.',
    )

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'
        ordering = ('name',)

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]
