from django.db import models

from .abstract import TimestampModel
from .artist_profile import ArtistProfile
from users.constants import (
    ADDRESS_FIELD_MAX_LENGTH,
    CITY_FIELD_MAX_LENGTH,
    MAX_CDEK_CODE_LENGTH,
)


class ArtistShippingPoint(TimestampModel):
    """Точка отправки заказов артиста (СДЭК)."""

    artist = models.OneToOneField(
        ArtistProfile,
        on_delete=models.CASCADE,
        related_name='shipping_point',
        verbose_name='Артист',
    )
    pvz_code = models.CharField(
        'Код ПВЗ СДЭК для отправки',
        max_length=MAX_CDEK_CODE_LENGTH,
    )
    city_code = models.CharField(
        'Код населенного пункта СДЭК',
        max_length=MAX_CDEK_CODE_LENGTH,
    )
    city = models.CharField(
        'Название населенного пункта',
        max_length=CITY_FIELD_MAX_LENGTH,
    )
    address = models.CharField(
        'Строка адреса',
        max_length=ADDRESS_FIELD_MAX_LENGTH,
    )

    class Meta:
        verbose_name = 'точка отправки заказов'
        verbose_name_plural = 'точка отправки заказов'

    def __str__(self):
        return f'{self.city} ({self.sdek_pvz_code})'
