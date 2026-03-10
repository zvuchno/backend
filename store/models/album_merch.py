from django.db import models

from store.models import Album, Merch
from users.models.abstract import ActivatableModel, TimestampModel


class AlbumMerch(ActivatableModel, TimestampModel):
    """Модель для связи альбома и мерча."""
    album = models.ForeignKey(Album, on_delete=models.SET_NULL, null=True)
    merch = models.ForeignKey(Merch, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['album', 'merch'],
                                    name='unique_album_merch')
        ]
        ordering = ['-created_at']
        verbose_name = 'Альбом и мерч'
        verbose_name_plural = 'Альбомы и мерчи'
