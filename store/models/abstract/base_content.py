"""Модуль базовых моделей контента.

Содержит абстрактную модель BaseContent с общими полями для всех
типов контента (название, описание, владелец, метки активности и времени).
Предназначена для наследования моделями Album, Track и другими.
"""

from django.contrib.auth import get_user_model
from django.db import models

from store.constants import MAX_CHAR_LENGTH
from users.models.abstract import ActivatableModel, TimestampModel

User = get_user_model()


class BaseContent(ActivatableModel, TimestampModel):
    """Абстрактная модель для моделей контента."""

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    description = models.TextField('Описание', blank=True, default='')

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        verbose_name='Артист',
    )

    class Meta:
        abstract = True
