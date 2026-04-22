"""Модель музыкального трека, входящего в состав альбома."""

from django.core.validators import FileExtensionValidator
from django.db import models

from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_STR_LENGTH,
)
from store.models.abstract import BaseContent
from store.querysets.track_visibility import TrackQuerySet


class Track(BaseContent):
    """Музыкальный трек в составе альбома.

    Связан с альбомом и пользователем-владельцем.
    """

    album = models.ForeignKey(
        'store.Album',
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Альбом',
    )
    audio_file = models.FileField(
        'Файл трека',
        upload_to='tracks/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
            ),
        ],
        help_text='Аудиофайл',
    )
    duration = models.PositiveIntegerField(
        'Длительность',
        null=True,
        blank=True,
        help_text='Длительность трека в секундах',
    )
    position = models.PositiveIntegerField(
        'Порядок',
        null=True,
        blank=True,
        help_text='Порядковый номер трека в альбоме',
    )
    lyrics = models.TextField('Текст трека', blank=True, default='')

    objects = TrackQuerySet.as_manager()

    class Meta:
        verbose_name = 'трек'
        verbose_name_plural = 'треки'
        ordering = ('album', 'position', 'name')

    def __str__(self):
        if self.position is not None:
            return f'{self.position}. {self.name[:MAX_STR_LENGTH]}'
        return self.name[:MAX_STR_LENGTH]
