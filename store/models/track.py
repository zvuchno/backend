"""
Модель музыкального трека, входящего в состав альбома.

Связан с альбомом и пользователем-владельцем.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator, MinValueValidator

from .album import Album
from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MAX_STR_LENGTH,
    PRICE_DECIMAL_PLACES,
)
from users.models.abstract import ActivatableModel, TimestampModel

User = get_user_model()


class Track(ActivatableModel, TimestampModel):
    """Музыкальный трек в составе альбома."""

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    album = models.ForeignKey(
        Album,
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Альбом',
    )
    audio_file = models.FileField(
        'Файл трека',
        upload_to='tracks/',
        validators=[FileExtensionValidator(
            allowed_extensions=ALLOWED_AUDIO_EXTENSIONS
        )],
        help_text='Аудиофайл'
        )
    duration = models.PositiveIntegerField(
        'Длительность',
        null=True,
        blank=True,
        help_text='Длительность трека в секундах'
    )
    track_number = models.PositiveIntegerField(
        'Номер трека',
        null=True,
        blank=True,
        help_text='Порядок трека в альбоме'
    )
    individual_price = models.DecimalField(
        'Цена трека',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Цена, руб.',
    )
    allow_fans_overpay = models.BooleanField(
        'Разрешить платить больше',
        default=False,
        help_text='Если включено, фанаты смогут заплатить больше стоимости.',
    )
    lyrics = models.TextField('Текст трека', blank=True, default='')
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Владелец',
    )

    class Meta:
        verbose_name = 'трек'
        verbose_name_plural = 'треки'
        ordering = ('album', 'track_number', 'name',)
        constraints = [
            models.UniqueConstraint(
                fields=['album', 'track_number'],
                name='unique_track_number_per_album')
        ]

    def __str__(self):
        if self.track_number is not None:
            return f'{self.track_number}. {self.name[:MAX_STR_LENGTH]}'
        return self.name[:MAX_STR_LENGTH]
