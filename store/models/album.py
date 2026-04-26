"""Музыкальный альбом или сингл исполнителя.

Альбом объединяет один или несколько треков и содержит метаданные
релиза.
"""

from django.db import models

from store.constants import MAX_STR_LENGTH
from store.models.abstract import BaseContent, VisibilityModel
from store.querysets import VisibilityQuerySet
from store.validators import validate_file_size


class Album(BaseContent, VisibilityModel):
    """Музыкальный альбом."""

    release_date = models.DateField('Дата релиза', blank=True, null=True)
    genre = models.ForeignKey(
        'store.Genre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Жанр',
        related_name='albums',
    )
    is_single = models.BooleanField('Сингл', default=False)
    cover_image = models.ImageField(
        'Обложка релиза',
        upload_to='album_covers',
        blank=True,
        null=True,
        validators=(validate_file_size,),
    )
    objects = VisibilityQuerySet.as_manager()

    class Meta:
        verbose_name = 'альбом'
        verbose_name_plural = 'альбомы'
        ordering = ('-created_at',)

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]
