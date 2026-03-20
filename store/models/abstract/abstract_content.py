"""Модуль базовых моделей контента.

Содержит абстрактную модель AbstractContent с общими полями для всех
типов контента (название, описание, владелец, метки активности и времени).
Предназначена для наследования моделями Album, Track и другими.
"""

from django.db import models

from store.constants import MAX_CHAR_LENGTH
from users.models import ArtistProfile
from users.models.abstract import ActivatableModel, TimestampModel


class AbstractContent(ActivatableModel, TimestampModel):
    """Абстрактная модель для моделей контента."""

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    description = models.TextField('Описание', blank=True, default='')

    owner = models.ForeignKey(
        ArtistProfile,
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        verbose_name='Артист',
    )

    class Meta:
        abstract = True
