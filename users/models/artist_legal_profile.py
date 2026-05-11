"""Модель юридического профиля артиста.

TODO: валидация комбинаций всех данных.
"""

from django.conf import settings
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from common.utils import normalize_email

from .abstract import TimestampModel
from users.constants import (
    RECIPIENT_TYPE_MAX_LENGTH,
)
from users.querysets import ArtistLegalProfileQuerySet


class ArtistLegalProfile(TimestampModel):
    """Юридический профиль артиста.

    Хранит служебные данные, связанные с идентификацией артиста
    как получателя выплат: тип получателя,
    статус проверки и комментарий модератора.

    Не предназначен для публичного отображения.
    """

    objects = ArtistLegalProfileQuerySet.as_manager()

    class RecipientType(models.TextChoices):
        EMPTY = '', 'Не указано'
        INDIVIDUAL_ENTREPRENEUR = 'individual_entrepreneur', 'ИП'
        SELF_EMPLOYED = 'self_employed', 'СМЗ'
        LEGAL_ENTITY = 'legal_entity', 'Юридическое лицо'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='legal_profile',
        verbose_name='Учетная запись',
    )

    email = models.EmailField(
        'Email для юридических документов',
        blank=True,
    )
    phone = PhoneNumberField(
        'Телефон для юридических документов',
        blank=True,
        null=True,
    )

    recipient_type = models.CharField(
        'Организационная форма',
        max_length=RECIPIENT_TYPE_MAX_LENGTH,
        choices=RecipientType.choices,
        blank=True,
        default='',
    )

    is_verified = models.BooleanField(
        'Проверено',
        default=False,
        help_text='Данные проверены вручную.',
    )

    comment = models.TextField(
        'Комментарий модератора',
        blank=True,
    )

    class Meta:
        verbose_name = 'юридический профиль артиста'
        verbose_name_plural = 'юридические профили артистов'
        ordering = ('-updated_at',)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Юридический профиль: {self.user.username}'
