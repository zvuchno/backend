from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

from .album import Album
from ..constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MAX_STR_LENGTH,
    PRICE_DECIMAL_PLACES,
)

User = get_user_model()


class Track(models.Model):
    """Музыкальный трек в составе альбома."""

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    album = models.ForeignKey(
        Album,
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Альбом'
        )
    audio_file = models.FileField(
        'Файл трека',
        upload_to='tracks/',
        help_text='Аудиофайл'
        )
    individual_price = models.DecimalField(
        'Цена трека',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Цена, руб.'
    )
    allow_fans_to_pay_more = models.BooleanField(
        'Разрешить платить больше',
        default=False,
        help_text='Если включено, фанаты смогут заплатить больше стоимости.'
    )
    lyrics = models.TextField('Текст трека', blank=True, default='')
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Владелец'
    )

    class Meta:
        verbose_name = 'трек'
        verbose_name_plural = 'Треки'
        ordering = ('album', 'name',)

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]
