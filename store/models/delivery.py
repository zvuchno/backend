"""Модели доставки."""

from decimal import Decimal

from django.db import models

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
)
from users.models.abstract import ActivatableModel, TimestampModel


class Delivery(ActivatableModel, TimestampModel):
    """Модель вариантов доставки."""

    class DeliveryType(models.TextChoices):
        PICKPOINT = 'pickpoint', 'Пункт выдачи'
        PICKUP = 'pickup', 'Самовывоз'
        COURIER = 'courier', 'Курьер до двери'
        POST = 'post', 'Почта'

    delivery_type = models.CharField(
        'Тип доставки',
        max_length=20,
        choices=DeliveryType.choices,
    )
    name = models.CharField('Название', max_length=100)
    price = models.DecimalField(
        'Стоимость (руб.)',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=Decimal('0.0000'),
    )
    description = models.TextField('Описание')

    class Meta:
        verbose_name = 'доставка'
        verbose_name_plural = 'доставки'

    def __str__(self):
        return self.name
