"""Модуль базовой модели контента."""

from django.conf import settings
from django.db import models

from store.constants import MAX_CHAR_LENGTH
from users.models.abstract import ActivatableModel, TimestampModel


class BaseContent(ActivatableModel, TimestampModel):
    """Абстрактная модель для моделей контента.

    Содержит общие поля для всех типов контента:
    название, описание, владелец, признак активности и временные метки.
    Предназначена для наследования моделями, такими как Album, Track и другими.
    """

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    description = models.TextField('Описание', blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_%(class)s_items',
        null=True,
        blank=True,
        editable=False,
        verbose_name='Создал',
    )

    class Meta:
        abstract = True


class ArtistContent(BaseContent):
    """Контент, размещённый в каталоге артиста."""

    artist = models.ForeignKey(
        'users.ArtistProfile',
        on_delete=models.PROTECT,
        related_name='%(class)s_items',
        verbose_name='Артист',
    )

    payout_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payout%(class)s_items',
        verbose_name='Получатель выплат',
    )

    class Meta:
        abstract = True
