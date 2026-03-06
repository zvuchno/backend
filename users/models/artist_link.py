from django.core.validators import MinLengthValidator
from django.db import models

from ..constants import (
    ARTIST_LINK_LABEL_MAX_LENGTH, ARTIST_LINK_LABEL_MIN_LENGTH,
    ARTIST_LINK_FIELD_MAX_LENGTH, ARTIST_LINK_FIELD_MIN_LENGTH,
    ARTIST_LINK_TYPE_MAX_LENGTH
)
from .abstract import ActivatableModel, TimestampModel


class LinkType(models.TextChoices):
    """Типы контактов."""
    CONTACT = 'contact', 'Контакт'
    SOCIAL = 'social', 'Соцсеть'


class ArtistLink(ActivatableModel, TimestampModel):
    """Контакт или ссылка на соцсеть артиста."""

    artist = models.ForeignKey(
        'ArtistProfile',
        on_delete=models.CASCADE,
        related_name='links',
        verbose_name='Артист'
    )

    link_type = models.CharField(
        'Тип ссылки',
        max_length=ARTIST_LINK_TYPE_MAX_LENGTH,
        choices=LinkType,
    )
    label = models.CharField(
        'Название',
        max_length=ARTIST_LINK_LABEL_MAX_LENGTH,
        validators=[MinLengthValidator(ARTIST_LINK_LABEL_MIN_LENGTH)],
    )
    value = models.CharField(
        'Значение',
        max_length=ARTIST_LINK_FIELD_MAX_LENGTH,
        validators=[MinLengthValidator(ARTIST_LINK_FIELD_MIN_LENGTH)],
    )

    class Meta:
        verbose_name = 'Ссылка артиста'
        verbose_name_plural = 'ссылки артиста'
        ordering = ['-created_at', 'link_type', 'label', 'value']

    def __str__(self):
        return f'{self.label}: {self.value}'
