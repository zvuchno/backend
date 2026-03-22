"""Модуль модели Product для монетизации контента.

Содержит универсальную карточку товара, используемую
как точка входа для коммерческой логики.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


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

    product_type = models.CharField(max_length=20, choices=ProductType.choices)
    allow_overpay = models.BooleanField(
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
    carriers = models.ManyToManyField(
        'store.Carrier',
        through='store.ProductVariant',
        related_name='products',
    )

    def determine_product_type(self):
        """Автозаполнение поля product_type.

        Автоматически определяет категорию товара на основе заполненной связи.
        """
        filled = (self.album, self.track, self.merch)
        if sum(map(bool, filled)) != 1:
            raise ValidationError(
                'Должен быть указан ровно один тип продукта.',
            )

        if self.album:
            self.product_type = self.ProductType.ALBUM
        elif self.track:
            self.product_type = self.ProductType.TRACK
        elif self.merch:
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
