"""Модель юридического профиля артиста."""

from django.conf import settings
from django.db import models

from .abstract import TimestampModel
from users.constants import (
    COMMENT_MAX_LENGTH,
    RECIPIENT_TYPE_MAX_LENGTH,
    TAXATION_SYSTEM_MAX_LENGTH,
)


class ArtistLegalProfile(TimestampModel):
    """Юридический профиль артиста.

    Хранит служебные данные, связанные с идентификацией артиста
    как получателя выплат: тип получателя, систему налогообложения,
    статус проверки и комментарий модератора.

    Не предназначен для публичного отображения.
    """

    class TaxationSystem(models.TextChoices):
        EMPTY = '', 'Не указано'
        NPD = 'npd', 'НПД (самозанятый)'
        USN = 'usn', 'УСН'
        OSNO = 'osno', 'ОСНО'
        PATENT = 'patent', 'Патент'

    class RecipientType(models.TextChoices):
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

    comment = models.CharField(
        'Комментарий модератора',
        max_length=COMMENT_MAX_LENGTH,
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = 'юридический профиль артиста'
        verbose_name_plural = 'юридические профили артистов'
        ordering = ('-updated_at',)

    def __str__(self):
        return f':Юридический профиль {self.user.username}'
