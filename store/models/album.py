"""
Музыкальный альбом или сингл исполнителя.

Альбом объединяет один или несколько треков и содержит метаданные
релиза.
"""

from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

from .genre import Genre
from ..constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MAX_STR_LENGTH,
    PRICE_DECIMAL_PLACES,
)
from .abstract import VisibilityModel
from store.validators import validate_file_size
from users.models.abstract import ActivatableModel, TimestampModel


User = get_user_model()


class Album(ActivatableModel, TimestampModel, VisibilityModel):
    """Музыкальный альбом."""

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    release_date = models.DateField('Дата релиза')
    genre = models.ForeignKey(
        Genre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Жанр',
        related_name='albums'
        )
    is_single = models.BooleanField('Сингл', default=False)
    price = models.DecimalField(
        'Цена',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Цена, руб.'
    )
    allow_fans_overpay = models.BooleanField(
        'Разрешить платить больше',
        default=False,
        help_text='Если включено, фанаты смогут заплатить больше стоимости.'
    )
    description = models.TextField('Описание', blank=True, default='')
    cover_image = models.ImageField(
        'Обложка релиза',
        upload_to='album_covers',
        blank=True,
        null=True,
        validators=(validate_file_size,)
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='albums',
        verbose_name='Владелец'
    )

    class Meta:
        verbose_name = 'альбом'
        verbose_name_plural = 'альбомы'
        ordering = ('-release_date',)

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]
