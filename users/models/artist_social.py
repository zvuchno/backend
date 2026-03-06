from django.core.validators import MinLengthValidator
from django.db import models

from ..constants import (
    ARTIST_LINK_LABEL_MAX_LENGTH, ARTIST_LINK_LABEL_MIN_LENGTH,
    ARTIST_LINK_FIELD_MAX_LENGTH, ARTIST_LINK_FIELD_MIN_LENGTH,
    ARTIST_LINK_TYPE_MAX_LENGTH
)
from .abstract import ActivatableModel, TimestampModel


class ArtistSocial(ActivatableModel, TimestampModel):
    """Контакт или ссылка на соцсеть артиста."""

    artist = models.ForeignKey(
        'ArtistProfile',
        on_delete=models.CASCADE,
        related_name='socials',
        verbose_name='Артист'
    )
    label = models.CharField(
        'Название соцсети',
        max_length=ARTIST_LINK_LABEL_MAX_LENGTH,
        validators=[MinLengthValidator(ARTIST_LINK_LABEL_MIN_LENGTH)],
    )
    value = models.URLField('Ссылка')

    class Meta:
        verbose_name = 'Соцсеть артиста'
        verbose_name_plural = 'соцсети артиста'
        ordering = ['-created_at', 'label', 'value']

    def __str__(self):
        return f'{self.label}: {self.value}'
