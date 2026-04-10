"""Модели доставки."""

from decimal import Decimal

from django.db import models

from store.constants import (
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)
from users.models.abstract import ActivatableModel, TimestampModel


class Delivery(ActivatableModel, TimestampModel):
    """Модель вариантов доставки."""

    name = models.CharField('Название', max_length=100)
    price = models.DecimalField(
        'Стоимость (руб.)',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        default=Decimal('0.00'),
    )
    description = models.TextField('Описание')

    class Meta:
        verbose_name = 'доставка'
        verbose_name_plural = 'доставки'

    def __str__(self):
        return self.name
