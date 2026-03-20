"""Модуль коммерческой логики приложения Store.

Содержит модель Product — универсальную модель для монетизации контента.
Вместо создания отдельных полей цен в моделях Album, Track и Merch,
используется единая точка входа.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from store.constants import (
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)


class Product(models.Model):
    """Универсальная карточка товара.

    Архитектурные особенности:
    1. Полиморфизм через Nullable OneToOneFields: модель может ссылаться
    ровно на один объект контента (альбом, трек и т.д.).
    2. Автоматическая типизация: поле 'type' заполняется в методе save()
    на основе активной связи.
    3. Целостность на уровне БД: CheckConstraint гарантирует, что товар
    не может быть привязан к двум объектам одновременно и что поле 'type'
    всегда соответствует заполненной связи.
    """

    class ProductType(models.TextChoices):
        TRACK = 'track', 'Track'
        ALBUM = 'album', 'Album'
        MERCH = 'merch', 'Merch'

    type = models.CharField(max_length=20, choices=ProductType.choices)
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
    album = models.OneToOneField(
        'store.Album',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product',
    )
    track = models.OneToOneField(
        'store.Track',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product',
    )
    merch = models.OneToOneField(
        'store.Merch',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product',
    )

    def determine_type(self):
        """Автозаполнение поля type.

        Автоматически определяет категорию товара на основе заполненной связи.
        """
        filled = (self.album, self.track, self.merch)
        if sum(bool(x) for x in filled) != 1:
            raise ValidationError(
                'Должен быть указан ровно один тип продукта.',
            )

        if self.album:
            self.type = self.ProductType.ALBUM
        elif self.track:
            self.type = self.ProductType.TRACK
        elif self.merch:
            self.type = self.ProductType.MERCH

    def save(self, *args, **kwargs):
        self.determine_type()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'
        constraints = [
            models.CheckConstraint(
                condition=(
                    # Вариант 1: Тип альбом -> заполнено только поле album
                    models.Q(
                        type='album',
                        album__isnull=False,
                        track__isnull=True,
                        merch__isnull=True,
                    )
                    |
                    # Вариант 2: Тип трек -> заполнено только поле track
                    models.Q(
                        type='track',
                        album__isnull=True,
                        track__isnull=False,
                        merch__isnull=True,
                    )
                    |
                    # Вариант 3: Тип мерч -> заполнено только поле merch
                    models.Q(
                        type='merch',
                        album__isnull=True,
                        track__isnull=True,
                        merch__isnull=False,
                    )
                ),
                name='%(app_label)s_%(class)s_target_integrity',
            ),
        ]

    def __str__(self):
        return ''
