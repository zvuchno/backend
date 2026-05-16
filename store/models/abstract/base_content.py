"""Модуль базовой модели контента."""

from django.contrib.auth import get_user_model
from django.db import models

from store.constants import MAX_CHAR_LENGTH
from users.models.abstract import ActivatableModel, TimestampModel

User = get_user_model()


class BaseContent(ActivatableModel, TimestampModel):
    """Абстрактная модель для моделей контента.

    Содержит общие поля для всех типов контента:
    название, описание, владелец, признак активности и временные метки.
    Предназначена для наследования моделями, такими как Album, Track и другими.
    """

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
