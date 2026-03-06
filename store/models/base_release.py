from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator


from ..constants import (
    MAX_CHAR_LENGTH,
    PRICE_DECIMAL_PLACES,
    MAX_PRICE_DIGITS,
)

User = get_user_model()


class BaseRelease(models.Model):
    """Абстрактная модель для альбома/сингла."""

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
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

    class Meta:
        abstract = True
