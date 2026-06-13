from django.db import models

from .abstract import ActivatableModel, TimestampModel
from .artist_profile import ArtistProfile
from users.constants import ADDRESS_FIELD_MAX_LENGTH


class ArtistPickupPoint(ActivatableModel, TimestampModel):
    """Модель точки самовывоза артиста.

    Артист может иметь несколько точек самовывоза,
    каждая с адресом и датой доступности.
    """

    artist = models.ForeignKey(
        ArtistProfile,
        on_delete=models.CASCADE,
        related_name='pickup_points',
        verbose_name='Артист',
    )
    address = models.CharField(
        'Адрес',
        max_length=ADDRESS_FIELD_MAX_LENGTH,
    )
    pickup_date = models.DateField(
        'Дата',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'пункт самовывоза артиста'
        verbose_name_plural = 'пункты самовывоза артистов'
        ordering = ('id',)

    def __str__(self):
        return f'Самовывоз: {self.address}'
