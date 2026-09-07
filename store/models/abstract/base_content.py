"""Модуль базовой модели контента."""

from django.conf import settings
from django.db import models

from common.models.abstract import ActivatableModel, TimestampModel

from store.constants import MAX_CHAR_LENGTH


class BaseContent(ActivatableModel, TimestampModel):
    """Абстрактная модель общего контента.

    Содержит название, описание, создателя, признак активности
    и временные метки.
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
