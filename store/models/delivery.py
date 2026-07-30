"""Модели доставки."""

from django.db import models

from store.constants import MAX_CHAR_LENGTH
from users.models.abstract import ActivatableModel, TimestampModel


class Delivery(ActivatableModel, TimestampModel):
    """Модель вариантов доставки."""

    class DeliveryType(models.TextChoices):
        COURIER = 'courier', 'СДЭК - курьером до двери'
        PICKPOINT = 'pickpoint', 'СДЭК - в пункт выдачи'
        ARTIST_PICKUP = 'artist_pickup', 'Самовывоз от артиста'

    delivery_type = models.CharField(
        'Тип доставки',
        max_length=20,
        choices=DeliveryType.choices,
    )
    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)

    class Meta:
        verbose_name = 'доставка'
        verbose_name_plural = 'доставки'

    def __str__(self):
        return self.get_delivery_type_display()
