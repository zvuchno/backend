"""
Модуль модели Избранного.
Позволяет пользователю отслеживать товары, которые он помечает как избранные.
"""

from django.conf import settings
from django.db import models

from users.models.abstract.activatable_model import ActivatableModel
from users.models.abstract.timestamp_model import TimestampModel


class Favorite(ActivatableModel, TimestampModel):
    """Модель избранного"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Пользователь',
    )
    product_variant = models.ForeignKey(
        'store.ProductVariant',
        verbose_name='Вариант продукта',
        related_name='favorited_by',
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = 'избранное'
        verbose_name_plural = 'избранные'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product_variant'],
                name='unique_favorite_per_user',
            )
        ]

    def __str__(self):
        return f'{self.product_variant}'
