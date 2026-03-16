"""Модель контактных данных артиста."""

from django.core.validators import MinLengthValidator
from django.db import models

from .abstract import ActivatableModel, TimestampModel
from users.constants import (
    ARTIST_LINK_LABEL_MAX_LENGTH,
    ARTIST_LINK_LABEL_MIN_LENGTH,
)


class ArtistContact(ActivatableModel, TimestampModel):
    """Контактные данные артиста.

    Связаны с профилем артиста и хранят название контакта
    и его значение. В текущей реализации в качестве значения
    используется адрес электронной почты.
    """

    artist = models.ForeignKey(
        'ArtistProfile',
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name='Артист',
    )
    label = models.CharField(
        'Название контакта',
        max_length=ARTIST_LINK_LABEL_MAX_LENGTH,
        validators=[MinLengthValidator(ARTIST_LINK_LABEL_MIN_LENGTH)],
    )
    value = models.EmailField('Контакт')

    class Meta:
        verbose_name = 'контакт артиста'
        verbose_name_plural = 'контакты артиста'
        ordering = ('-created_at', 'label', 'value')

    def __str__(self):
        return f'{self.label}: {self.value}'
