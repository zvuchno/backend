"""Модель музыкального трека, входящего в состав альбома.

Связан с альбомом и пользователем-артистом.
"""

from django.core.validators import FileExtensionValidator
from django.db import models

from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_STR_LENGTH,
)
from store.models.abstract import AbstractContent


class Track(AbstractContent):
    """Музыкальный трек в составе альбома."""

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
    track_number = models.PositiveIntegerField(
        'Номер трека',
        null=True,
        blank=True,
        help_text='Порядок трека в альбоме',
    )
    lyrics = models.TextField('Текст трека', blank=True, default='')

    class Meta:
        verbose_name = 'трек'
        verbose_name_plural = 'треки'
        ordering = ('album', 'track_number', 'name')

    def __str__(self):
        if self.track_number is not None:
            return f'{self.track_number}. {self.name[:MAX_STR_LENGTH]}'
        return self.name[:MAX_STR_LENGTH]
