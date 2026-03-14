"""Модели ссылок на соцсети артиста.

Модуль содержит модель, которая хранит внешние ссылки,
связанные с профилем артиста, например ссылки на соцсети
или другие публичные страницы.
"""

from django.core.validators import MinLengthValidator
from django.db import models

from .abstract import ActivatableModel, TimestampModel
from users.constants import (
    ARTIST_LINK_LABEL_MAX_LENGTH,
    ARTIST_LINK_LABEL_MIN_LENGTH,
)


class ArtistSocial(ActivatableModel, TimestampModel):
    """Ссылка на соцсеть или внешний ресурс артиста.

    Связана с профилем артиста и хранит название ссылки
    и ее URL. Используется для отображения публичных
    ресурсов артиста в его профиле.
    """

    artist = models.ForeignKey(
        'ArtistProfile',
        on_delete=models.CASCADE,
        related_name='socials',
        verbose_name='Артист',
    )
    label = models.CharField(
        'Название соцсети',
        max_length=ARTIST_LINK_LABEL_MAX_LENGTH,
        validators=[MinLengthValidator(ARTIST_LINK_LABEL_MIN_LENGTH)],
    )
    value = models.URLField('Ссылка')

    class Meta:
        verbose_name = 'соцсеть артиста'
        verbose_name_plural = 'соцсети артиста'
        ordering = ('-created_at', 'label', 'value')

    def __str__(self):
        """Возвращает строковое представление ссылки артиста."""
        return f'{self.label}: {self.value}'
