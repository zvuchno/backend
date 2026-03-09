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

User = get_user_model()


class Album(models.Model):
    """Музыкальный альбом."""

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Опубликовано'
        LINK_ONLY = 'link_only', 'Доступно по ссылке'
        HIDDEN = 'hidden', 'Скрыто'

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
    price = models.DecimalField(
        'Цена',
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
    description = models.TextField('Описание', blank=True, default='')
    cover_image = models.ImageField(
        'Обложка релиза',
        upload_to='album_covers',
        blank=True,
        null=True,
    )
    visibility = models.CharField(
        'Приватность',
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='albums',
        verbose_name='Владелец'
    )

    class Meta:
        verbose_name = 'альбом'
        verbose_name_plural = 'Альбомы'
        ordering = ('-release_date',)

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]
