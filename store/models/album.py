"""Музыкальный альбом или сингл исполнителя.

Альбом объединяет один или несколько треков и содержит метаданные
релиза.
"""

from django.contrib.auth import get_user_model
from django.db import models

from .genre import Genre
from store.constants import MAX_STR_LENGTH
from store.models.abstract import AbstractContent
from store.validators import validate_file_size

User = get_user_model()


class Album(AbstractContent):
    """Музыкальный альбом."""

    release_date = models.DateField('Дата релиза')
    genre = models.ForeignKey(
        Genre,
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
    product = models.OneToOneField(
        'models.Product',
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='album',
    )

    class Meta:
        verbose_name = 'альбом'
        verbose_name_plural = 'альбомы'
        ordering = ('-release_date',)

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]
