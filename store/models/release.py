from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator


from ..constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MAX_STR_LENGHT,
    PRICE_DECIMAL_PLACES,
)

User = get_user_model()


class Release(models.Model):
    """Музыкальный релиз."""

    class ReleaseType(models.TextChoices):
        SINGLE = 'single', 'Сингл'
        ALBUM = 'album', 'Альбом'

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Опубликовано'
        LINK_ONLY = 'link_only', 'Доступно по ссылке'
        HIDDEN = 'hidden', 'Скрыто'

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    release_type = models.CharField(
        'Тип релиза',
        max_length=10,
        choices=ReleaseType.choices
    )
    release_date = models.DateField('Дата релиза')
    genre = models.CharField('Жанр', max_length=MAX_CHAR_LENGTH)
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
    description = models.TextField('Описание', blank=True, null=True)
    cover_image = models.ImageField(
        'Обложка релиза',
        upload_to='release_covers',
        blank=True,
        null=True,
    )
    visibility = models.CharField(
        'Приватность',
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='releases'
    )

    class Meta:
        verbose_name = 'релиз'
        verbose_name_plural = 'Релизы'

    def __str__(self):
        return self.name[:MAX_STR_LENGHT]
