from django.db import models

from store.models.album import Album
from store.models.merch import Merch
from users.models.abstract import ActivatableModel, TimestampModel


class AlbumMerch(ActivatableModel, TimestampModel):
    """Модель для связи альбома и мерча."""

    album = models.ForeignKey(
        Album, on_delete=models.SET_NULL, null=True, verbose_name='Альбом'
    )
    merch = models.ForeignKey(
        Merch, on_delete=models.CASCADE, verbose_name='Мерч'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['album', 'merch'],
                                    name='unique_album_merch')
        ]
        ordering = ['-created_at']
        verbose_name = 'альбом и мерч'
        verbose_name_plural = 'альбомы и мерчи'
        default_related_name = 'album_merch'
