"""Музыкальный альбом или сингл исполнителя.

Альбом объединяет один или несколько треков и содержит метаданные
релиза.
"""

from django.db import models

from common.storages import get_private_media_storage, get_public_media_storage

from store.constants import MAX_STR_LENGTH
from store.models.abstract import BaseContent, VisibilityModel
from store.querysets import VisibilityQuerySet
from store.upload_paths import album_archive_upload_to, album_cover_upload_to
from store.validators import validate_file_size
from users.models.abstract import TimestampModel


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
        upload_to=album_cover_upload_to,
        storage=get_public_media_storage,
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


class AlbumArchive(TimestampModel):
    """Подготовленный архив альбома.

    `content_hash` хранит отпечаток исходных данных, из которых собран архив,
    а не хеш самого ZIP-файла.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает сборки'
        BUILDING = 'building', 'Собирается'
        READY = 'ready', 'Готов'
        FAILED = 'failed', 'Ошибка'

    album = models.OneToOneField(
        Album,
        on_delete=models.CASCADE,
        related_name='archive',
    )
    file = models.FileField(
        upload_to=album_archive_upload_to,
        storage=get_private_media_storage,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    content_hash = models.CharField(
        'Отпечаток содержимого архива',
        max_length=64,
        blank=True,
        help_text=(
            'SHA256 от нормализованного состава альбома, '
            'используется для проверки актуальности архива.'
        ),
    )
    pending_hash = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Хеш сборки для существующей задачи.',
    )
    error_message = models.TextField(blank=True)
