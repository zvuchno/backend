"""Модель юридического профиля артиста."""

from django.conf import settings
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from common.models.abstract import TimestampModel
from common.utils import normalize_email

from users.constants import (
    RECIPIENT_TYPE_MAX_LENGTH,
)
from users.querysets import ArtistLegalProfileQuerySet

IDENTITY_VERIFICATION_REQUIRED_FIELDS = (
    'last_name',
    'first_name',
    'birth_date',
    'registration_address',
    'passport_series',
    'passport_number',
    'passport_issued_by',
    'passport_issue_date',
    'inn',
)

COMPANY_VERIFICATION_REQUIRED_FIELDS = (
    'company_name',
    'company_address',
    'inn',
    'ogrn',
)

BANK_VERIFICATION_REQUIRED_FIELDS = (
    'bik',
    'checking_account',
)


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

    @property
    def is_ready_for_verification(self):
        """Показывает, достаточно ли данных для ручной проверки."""
        return not self.get_verification_missing_fields()

    class Meta:
        verbose_name = 'юридический профиль артиста'
        verbose_name_plural = 'юридические профили артистов'
        ordering = ('-updated_at',)

    def clean(self):
        super().clean()
        if self.email:
            self.email = normalize_email(self.email)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_verification_missing_fields(self):
        """Возвращает незаполненные поля, необходимые для проверки."""
        missing_fields = []

        if not self.recipient_type:
            missing_fields.append('recipient_type')

        bank_data = getattr(self, 'bank_data', None)
        missing_fields.extend(
            self._get_missing_related_fields(
                bank_data,
                BANK_VERIFICATION_REQUIRED_FIELDS,
                'bank_data',
            ),
        )

        if self.recipient_type in (
            self.RecipientType.SELF_EMPLOYED,
            self.RecipientType.INDIVIDUAL_ENTREPRENEUR,
        ):
            identity_data = getattr(self, 'identity_data', None)
            missing_fields.extend(
                self._get_missing_related_fields(
                    identity_data,
                    IDENTITY_VERIFICATION_REQUIRED_FIELDS,
                    'identity_data',
                ),
            )

        elif self.recipient_type == self.RecipientType.LEGAL_ENTITY:
            company_data = getattr(self, 'company_data', None)
            missing_fields.extend(
                self._get_missing_related_fields(
                    company_data,
                    COMPANY_VERIFICATION_REQUIRED_FIELDS,
                    'company_data',
                ),
            )

        return missing_fields

    @staticmethod
    def _get_missing_related_fields(instance, fields, prefix) -> list:
        """Возвращает незаполненные обязательные поля связанного объекта."""
        if instance is None:
            return [f'{prefix}.{field}' for field in fields]

        missing_fields = []

        for field in fields:
            value = getattr(instance, field)

            if ArtistLegalProfile._is_empty_value(value):
                missing_fields.append(f'{prefix}.{field}')

        return missing_fields

    @staticmethod
    def _is_empty_value(value) -> bool:
        """Проверяет, считается ли значение незаполненным."""
        if value is None:
            return True

        if isinstance(value, str):
            return not value.strip()

        return False

    def __str__(self):
        return f'Юридический профиль: {self.user.username}'
