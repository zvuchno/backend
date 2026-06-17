"""Модели доставки."""

from django.db import models

from users.models.abstract import ActivatableModel, TimestampModel


class Delivery(ActivatableModel, TimestampModel):
    """Модель вариантов доставки."""

    class DeliveryType(models.TextChoices):
        COURIER = 'courier', 'СДЭК - курьером до двери'
        PICKPOINT = 'pickpoint', 'СДЭК - в пункт выдачи'
        PICKUP = 'pickup', 'Самовывоз'

    delivery_type = models.CharField(
        'Тип доставки',
        max_length=20,
        choices=DeliveryType.choices,
    )
    name = models.CharField('Название', max_length=100)

    class Meta:
        verbose_name = 'доставка'
        verbose_name_plural = 'доставки'

    def __str__(self):
        return self.name
