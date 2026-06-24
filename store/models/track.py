"""Модель музыкального трека, входящего в состав альбома."""

from django.core.validators import FileExtensionValidator
from django.db import models

from common.storages import get_private_media_storage, get_public_media_storage

from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_FILE_STATUS_STR,
    MAX_STR_LENGTH,
)
from store.models.abstract import BaseContent
from store.querysets.track_visibility import TrackQuerySet
from store.upload_paths import (
    track_audio_upload_to,
    track_preview_upload_to,
    track_stream_upload_to,
)
from store.validators import validate_audiofile_size


class Track(BaseContent):
    """Музыкальный трек в составе альбома.

    Связан с альбомом и пользователем-владельцем.
    """

    class AudioProcessingStatus(models.TextChoices):
        PENDING = 'pending', 'Ожидает обработки'
        PROCESSING = 'processing', 'Обрабатывается'
        READY = 'ready', 'Готово'
        FAILED = 'failed', 'Ошибка обработки'

    album = models.ForeignKey(
        'store.Album',
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Альбом',
    )
    audio_file = models.FileField(
        'Файл трека',
        upload_to=track_audio_upload_to,
        storage=get_private_media_storage,
        validators=[
            FileExtensionValidator(
                allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
            ),
            validate_audiofile_size,
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

    preview_file = models.FileField(
        'Файл превью',
        upload_to=track_preview_upload_to,
        storage=get_public_media_storage,
        blank=True,
    )

    preview_status = models.CharField(
        'Статус подготовки превью',
        max_length=MAX_FILE_STATUS_STR,
        choices=AudioProcessingStatus.choices,
        default=AudioProcessingStatus.PENDING,
    )

    preview_error = models.TextField(
        'Ошибка подготовки превью',
        blank=True,
    )

    preview_started_at = models.DateTimeField(
        'Начало подготовки превью',
        blank=True,
        null=True,
    )

    stream_file = models.FileField(
        'Файл для воспроизведения',
        upload_to=track_stream_upload_to,
        storage=get_private_media_storage,
        blank=True,
    )

    stream_status = models.CharField(
        'Статус подготовки файла для воспроизведения',
        max_length=MAX_FILE_STATUS_STR,
        choices=AudioProcessingStatus.choices,
        default=AudioProcessingStatus.PENDING,
    )

    stream_error = models.TextField(
        'Ошибка подготовки файла для воспроизведения',
        blank=True,
    )

    stream_started_at = models.DateTimeField(
        'Начало подготовки файла для воспроизведения',
        blank=True,
        null=True,
    )

    objects = TrackQuerySet.as_manager()

    class Meta:
        verbose_name = 'трек'
        verbose_name_plural = 'треки'
        ordering = ('album', 'position', 'name')

    def __str__(self):
        if self.position is not None:
            return f'{self.position}. {self.name[:MAX_STR_LENGTH]}'
        return self.name[:MAX_STR_LENGTH]
