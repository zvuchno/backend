"""Модели музыкальных записей и треков в релизах."""

from django.core.validators import FileExtensionValidator
from django.db import models

from common.models.abstract import ActivatableModel, TimestampModel
from common.storages import get_private_media_storage, get_public_media_storage

from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_CHAR_LENGTH,
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
from store.validators import validate_audiofile_size, validate_isrc_format


class Recording(BaseContent):
    """Музыкальная запись, существующая независимо от конкретного релиза."""

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
        blank=True,
        help_text='Оригинальный аудиофайл трека.',
    )
    duration = models.PositiveIntegerField(
        'Длительность',
        null=True,
        blank=True,
        help_text='Длительность трека в секундах',
    )
    owner = models.ForeignKey(
        'users.ArtistProfile',
        on_delete=models.PROTECT,
        related_name='owned_recordings',
        verbose_name='Владелец записи',
        help_text='Профиль, управляющий мастер-записью.',
    )
    isrc = models.CharField(
        'ISRC',
        max_length=12,
        blank=True,
        default='',
        validators=(validate_isrc_format,),
        help_text='ISRC без дефисов, 12 символов.',
    )
    file_hash = models.CharField(
        'SHA-256 аудиофайла',
        max_length=64,
        blank=True,
        default='',
        db_index=True,
        editable=False,
        help_text='SHA-256 оригинального аудиофайла.',
    )

    class Meta:
        verbose_name = 'музыкальная запись'
        verbose_name_plural = 'музыкальные записи'
        ordering = ('name', 'id')

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]


class ReleaseTrack(ActivatableModel, TimestampModel):
    """Связь музыкального трека с релизом."""

    release = models.ForeignKey(
        'store.Album',
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Релиз',
    )
    recording = models.ForeignKey(
        'store.Recording',
        on_delete=models.PROTECT,
        related_name='release_tracks',
        verbose_name='Запись',
    )
    position = models.PositiveIntegerField(
        'Порядок',
        null=True,
        blank=True,
    )

    @property
    def name(self):
        return self.recording.name

    @property
    def artist(self):
        return self.release.artist

    @property
    def payout_recipient(self):
        return self.release.payout_recipient

    objects = TrackQuerySet.as_manager()

    def __str__(self):
        if self.position is not None:
            return f'{self.position}. {self.name[:MAX_STR_LENGTH]}'
        return self.name[:MAX_STR_LENGTH]

    class Meta:
        verbose_name = 'трек релиза'
        verbose_name_plural = 'треки релиза'
        ordering = ('release', 'position', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('release', 'recording'),
                name='unique_release_recording',
            ),
        ]


class TrackUpload(TimestampModel):
    """Попытка прямой загрузки оригинального файла трека."""

    class Status(models.TextChoices):
        """Статус попытки загрузки."""

        INITIATED = 'initiated', 'Ожидает загрузки'
        UPLOADED = 'uploaded', 'Файл загружен'
        COMPLETED = 'completed', 'Загрузка завершена'
        FAILED = 'failed', 'Ошибка загрузки'
        EXPIRED = 'expired', 'Срок загрузки истёк'

    class Purpose(models.TextChoices):
        """Назначение попытки загрузки."""

        CREATE = 'create', 'Создание трека'
        REPLACE = 'replace', 'Замена файла'

    track = models.ForeignKey(
        'store.Recording',
        on_delete=models.CASCADE,
        related_name='upload_attempts',
        verbose_name='Трек',
    )
    purpose = models.CharField(
        'Назначение загрузки',
        max_length=MAX_FILE_STATUS_STR,
        choices=Purpose.choices,
        default=Purpose.CREATE,
    )
    status = models.CharField(
        'Статус загрузки',
        max_length=MAX_FILE_STATUS_STR,
        choices=Status.choices,
        default=Status.INITIATED,
    )
    staging_key = models.CharField(
        'Ключ временного файла',
        max_length=500,
        unique=True,
    )
    original_filename = models.CharField(
        'Исходное имя файла',
        max_length=MAX_CHAR_LENGTH,
    )
    expected_size = models.PositiveBigIntegerField(
        'Ожидаемый размер файла',
    )
    content_type = models.CharField(
        'Заявленный MIME-тип',
        max_length=MAX_CHAR_LENGTH,
        blank=True,
    )
    uploaded_size = models.PositiveBigIntegerField(
        'Фактический размер файла',
        null=True,
        blank=True,
    )
    error = models.TextField(
        'Ошибка загрузки',
        blank=True,
    )
    expires_at = models.DateTimeField(
        'Срок действия загрузки',
    )
    completed_at = models.DateTimeField(
        'Завершено',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'загрузка трека'
        verbose_name_plural = 'загрузки треков'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.track}: {self.get_status_display()}'


class TrackGeneratedAudio(models.Model):
    """Результаты подготовки генерируемых аудиофайлов трека."""

    class ProcessingStatus(models.TextChoices):
        """Статус подготовки производного файла."""

        PENDING = 'pending', 'Ожидает подготовки'
        BUILDING = 'building', 'Подготавливается'
        READY = 'ready', 'Готов'
        FAILED = 'failed', 'Ошибка подготовки'

    track = models.OneToOneField(
        'store.Recording',
        on_delete=models.CASCADE,
        related_name='generated',
        verbose_name='Трек',
    )

    preview_file = models.FileField(
        'Файл превью',
        upload_to=track_preview_upload_to,
        storage=get_public_media_storage,
        blank=True,
    )
    preview_duration = models.PositiveIntegerField(
        'Длительность превью',
        null=True,
        blank=True,
        help_text='Длительность подготовленного превью в секундах',
    )
    preview_status = models.CharField(
        'Статус подготовки превью',
        max_length=MAX_FILE_STATUS_STR,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    preview_error = models.TextField(
        'Ошибка подготовки превью',
        blank=True,
    )
    preview_started_at = models.DateTimeField(
        'Начало подготовки превью',
        null=True,
        blank=True,
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
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    stream_error = models.TextField(
        'Ошибка подготовки файла для воспроизведения',
        blank=True,
    )
    stream_started_at = models.DateTimeField(
        'Начало подготовки файла для воспроизведения',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'сгенерированные аудиофайлы трека'
        verbose_name_plural = 'сгенерированные аудиофайлы треков'

    def __str__(self):
        return f'Обработка: {self.track}'
