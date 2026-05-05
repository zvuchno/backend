"""Модуль модели Product для монетизации контента.

Содержит универсальную карточку товара, используемую
как точка входа для коммерческой логики.
"""

import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import NoReverseMatch, reverse

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
)

logger = logging.getLogger(__name__)


class Product(models.Model):
    """Универсальная карточка товара.

    Архитектурные особенности:
    1. Полиморфизм через Nullable OneToOneFields: модель может ссылаться
    ровно на один объект контента (альбом, трек и т.д.).
    2. Автоматическая типизация: поле 'product_type' заполняется в методе
    save() на основе активной связи.
    3. Целостность на уровне БД: CheckConstraint гарантирует, что товар
    не может быть привязан к двум объектам одновременно и что поле
    'product_type' всегда соответствует заполненной связи.
    """

    class ProductType(models.TextChoices):
        TRACK = 'track', 'Track'
        ALBUM = 'album', 'Album'
        MERCH = 'merch', 'Merch'

    product_type = models.CharField(
        'Тип продукта',
        max_length=20,
        choices=ProductType.choices,
    )
    price = models.DecimalField(
        'Цена',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        validators=[MinValueValidator(Decimal('0.0000'))],
        default=Decimal('0.0000'),
        help_text='Цена, руб.',
    )
    allow_overpay = models.BooleanField(
        'Разрешить платить больше',
        default=False,
        help_text='Если включено, фанаты смогут заплатить больше стоимости.',
    )
    property_name = models.CharField(
        'Название свойства',
        max_length=MAX_CHAR_LENGTH,
        blank=True,
        null=True,
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

    @property
    def target_url(self):
        """Определяет URL в зависимости от того, какой контент привязан."""
        try:
            if self.album_id:
                return reverse(
                    'api:store:albums-detail',
                    kwargs={'pk': self.album_id},
                )
            if self.track_id:
                return reverse(
                    'api:store:tracks-detail',
                    kwargs={'pk': self.track_id},
                )
            if self.merch_id:
                # return reverse(
                #'api:store:merch-detail',
                # kwargs={'pk': self.merch_id},
                # )
                return (
                    f'/api/v1/store/merch/{self.merch_id}/'  # TODO: временно
                )
        except NoReverseMatch as e:
            logger.error(f'Ошибка формирования URL для Product {self.id}: {e}')
            return None
        return None

    def determine_product_type(self):
        """Автозаполнение поля product_type.

        Автоматически определяет категорию товара на основе заполненной связи.
        """
        filled_ids = (self.album_id, self.track_id, self.merch_id)
        if sum(map(bool, filled_ids)) != 1:
            raise ValidationError(
                'Должен быть указан ровно один тип продукта.',
            )

        if self.album_id:
            self.product_type = self.ProductType.ALBUM
        elif self.track_id:
            self.product_type = self.ProductType.TRACK
        elif self.merch_id:
            self.product_type = self.ProductType.MERCH

    def save(self, *args, **kwargs):
        self.determine_product_type()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    (
                        Q(product_type='album')
                        & Q(album__isnull=False)
                        & Q(track__isnull=True)
                        & Q(merch__isnull=True)
                    )
                    | (
                        Q(product_type='track')
                        & Q(track__isnull=False)
                        & Q(album__isnull=True)
                        & Q(merch__isnull=True)
                    )
                    | (
                        Q(product_type='merch')
                        & Q(merch__isnull=False)
                        & Q(album__isnull=True)
                        & Q(track__isnull=True)
                    ),
                ),
                name='%(app_label)s_%(class)s_integrity',
            ),
        ]

    def __str__(self):
        content_object = self.album or self.track or self.merch
        if not content_object:
            return f'Новый товар ({self.get_product_type_display()})'
        return f'{self.get_product_type_display()}: {content_object}'
