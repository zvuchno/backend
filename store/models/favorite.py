from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from users.models.abstract.timestamp_model import TimestampModel
from users.models.abstract.activatable_model import ActivatableModel
from .track import Track
from .album import Album
from .merch import Merch


class Favorite(ActivatableModel, TimestampModel):
    """Модель избранного"""

    listener = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Слушатель',
    )
    track = models.ForeignKey(
        'Track',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Трек',
    )
    album = models.ForeignKey(
        'Album',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Альбом',
    )
    merch = models.ForeignKey(
        'Merch',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Мерч',
    )

    class Meta:
        verbose_name = 'избранные'
        verbose_name_plural = 'избранное'
        default_related_name = 'favorited_by'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.content_object}'
