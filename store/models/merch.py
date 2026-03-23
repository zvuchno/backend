from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

from store.constants import (
    DEFAULT_QUANTITY,
    DESCRIPTION_MERCH_MAX_LENGTH,
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)
from store.models.abstract.visibility_model import VisibilityModel
from store.models.album import Album
from store.models.category import Category
from store.models.kind import Kind
from users.models.abstract import ActivatableModel, TimestampModel

User = get_user_model()


class Merch(ActivatableModel, TimestampModel, VisibilityModel):
    """Модель мерча."""

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='merch',
        verbose_name='Категория',
        null=True,
    )
    name = models.CharField(
        'Название',
        max_length=MAX_CHAR_LENGTH,
    )
    price = models.DecimalField(
        'Цена',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
    )
    allow_fans_overpay = models.BooleanField(
        'Разрешение платить больше',
        default=False,
    )
    quantity = models.PositiveIntegerField(
        'Количество',
        default=DEFAULT_QUANTITY,
    )
    kind = models.ForeignKey(
        Kind,
        on_delete=models.SET_NULL,
        verbose_name='Тип',
        related_name='merch',
        null=True,
    )
    description = models.TextField(
        'Описание',
        max_length=DESCRIPTION_MERCH_MAX_LENGTH,
        null=True,
        blank=True,
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Автор',
    )
    characteristic = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Свойства',
    )
    album = models.ManyToManyField(
        Album,
        blank=True,
        through='AlbumMerch',
        verbose_name='Альбом',
        related_name='merch',
    )

    class Meta:
        verbose_name = 'мерч'
        verbose_name_plural = 'мерчи'
        ordering = ('name',)

    def __str__(self):
        return self.name
