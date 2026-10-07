"""Модель бонусов."""

from django.core.validators import FileExtensionValidator
from django.db import models

from common.models.abstract import ActivatableModel, TimestampModel
from common.storages import get_public_media_storage

from store.constants import (
    ALLOWED_BONUS_EXTENSIONS,
    MAX_CHAR_LENGTH,
    MAX_STR_LENGTH,
)
from store.models import Album
from store.upload_paths import bonus_audio_upload_to
from store.validators import validate_bonusfile_size


class Bonus(ActivatableModel, TimestampModel):
    """Бонус для покупателя."""

    album = models.ForeignKey(
        Album,
        on_delete=models.CASCADE,
        related_name='bonuses',
        verbose_name='Альбом',
    )
    name = models.CharField(
        'Название бонуса',
        max_length=MAX_CHAR_LENGTH,
    )
    bonus_file = models.FileField(
        'Файл бонуса',
        upload_to=bonus_audio_upload_to,
        storage=get_public_media_storage,
        validators=(
            FileExtensionValidator(
                allowed_extensions=ALLOWED_BONUS_EXTENSIONS,
            ),
            validate_bonusfile_size,
        ),
    )
    description = models.TextField('Описание', blank=True, default='')

    class Meta:
        verbose_name = 'бонус'
        verbose_name_plural = 'бонусы'
        ordering = ('name',)

    def __str__(self):
        return f'{self.name[:MAX_STR_LENGTH]} [ id: {self.id} ]'
