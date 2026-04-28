"""Модель юридического профиля артиста."""

from django.conf import settings
from django.db import models

from common.fields import (
    EncryptedCharField,
)

from .abstract import TimestampModel
from users.constants import (
    NAME_FIELD_MAX_LENGTH,
    RECIPIENT_TYPE_MAX_LENGTH,
    TAXATION_SYSTEM_MAX_LENGTH,
)
from users.querysets import ArtistLegalProfileQuerySet


class ArtistLegalProfile(TimestampModel):
    """Юридический профиль артиста.

    Хранит служебные данные, связанные с идентификацией артиста
    как получателя выплат: тип получателя, систему налогообложения,
    статус проверки и комментарий модератора.

    Не предназначен для публичного отображения.
    """

    objects = ArtistLegalProfileQuerySet.as_manager()

    class TaxationSystem(models.TextChoices):
        EMPTY = '', 'Не указано'
        OSNO = 'osno', 'ОСНО'
        USN = 'usn', 'УСН'
        AUSN = 'ausn', 'АУСН'
        ESHN = 'eshn', 'ЕСХН'
        PATENT = 'patent', 'Патент'
        NPD = 'npd', 'НПД'

    class RecipientType(models.TextChoices):
        EMPTY = '', 'Не указано'
        INDIVIDUAL = 'individual', 'Физическое лицо'
        SELF_EMPLOYED = 'self_employed', 'Самозанятый'
        INDIVIDUAL_ENTREPRENEUR = 'individual_entrepreneur', 'ИП'
        LEGAL_ENTITY = 'legal_entity', 'Юридическое лицо'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='legal_profile',
        verbose_name='Учетная запись',
    )

    recipient_type = models.CharField(
        'Тип получателя',
        max_length=RECIPIENT_TYPE_MAX_LENGTH,
        choices=RecipientType.choices,
        default=RecipientType.EMPTY,
        blank=True,
    )
    recipient_name = EncryptedCharField(
        'Наименование получателя',
        max_length=NAME_FIELD_MAX_LENGTH,
        blank=True,
        null=True,
    )

    taxation_system = models.CharField(
        'Система налогообложения',
        max_length=TAXATION_SYSTEM_MAX_LENGTH,
        choices=TaxationSystem.choices,
        blank=True,
        default=TaxationSystem.EMPTY,
    )

    is_verified = models.BooleanField(
        'Проверено',
        default=False,
        help_text='Данные проверены вручную.',
    )

    comment = models.TextField(
        'Комментарий модератора',
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = 'юридический профиль артиста'
        verbose_name_plural = 'юридические профили артистов'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Юридический профиль: {self.user.username}'
