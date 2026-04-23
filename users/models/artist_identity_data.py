"""Модель паспортных данных артиста."""

from django.core.exceptions import ValidationError
from django.db import models

from .abstract import TimestampModel
from users.constants import (
    ADDRESS_FIELD_MAX_LENGTH,
    NAME_FIELD_MAX_LENGTH,
    PASSPORT_ISSUED_BY_MAX_LENGTH,
    PASSPORT_NUMBER_MAX_LENGTH,
    PASSPORT_SERIES_MAX_LENGTH,
)
from users.querysets import LegalDataQuerySet
from users.validators import (
    normalize_digits,
    validate_birth_date,
    validate_passport_issue_date,
    validate_passport_number,
    validate_passport_series,
)


class ArtistIdentityData(TimestampModel):
    """Паспортные данные артиста.

    Хранит ФИО, дату рождения, адрес регистрации и реквизиты
    документа, удостоверяющего личность. Используется для выплат,
    отчетности и юридической идентификации артиста.
    """

    objects = LegalDataQuerySet.as_manager()

    legal_profile = models.OneToOneField(
        'users.ArtistLegalProfile',
        on_delete=models.CASCADE,
        related_name='identity_data',
        verbose_name='Юридический профиль',
    )

    last_name = models.CharField(
        'Фамилия',
        max_length=NAME_FIELD_MAX_LENGTH,
    )
    first_name = models.CharField(
        'Имя',
        max_length=NAME_FIELD_MAX_LENGTH,
    )
    middle_name = models.CharField(
        'Отчество',
        max_length=NAME_FIELD_MAX_LENGTH,
        blank=True,
        default='',
    )
    birth_date = models.DateField(
        'Дата рождения',
        blank=True,
        null=True,
        validators=[validate_birth_date],
    )
    registration_address = models.CharField(
        'Адрес регистрации',
        max_length=ADDRESS_FIELD_MAX_LENGTH,
        blank=True,
        default='',
    )

    passport_series = models.CharField(
        'Серия паспорта',
        max_length=PASSPORT_SERIES_MAX_LENGTH,
        blank=True,
        default='',
        validators=[validate_passport_series],
    )
    passport_number = models.CharField(
        'Номер паспорта',
        max_length=PASSPORT_NUMBER_MAX_LENGTH,
        blank=True,
        default='',
        validators=[validate_passport_number],
    )
    passport_issued_by = models.CharField(
        'Кем выдан паспорт',
        max_length=PASSPORT_ISSUED_BY_MAX_LENGTH,
        blank=True,
        default='',
    )
    passport_issue_date = models.DateField(
        'Дата выдачи паспорта',
        blank=True,
        null=True,
        validators=[validate_passport_issue_date],
    )

    def save(self, *args, **kwargs):
        """Сохраняет объект после полной валидации модели."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Проверяет согласованность паспортных данных."""
        super().clean()

        if self.passport_series:
            self.passport_series = normalize_digits(self.passport_series)

        if self.passport_number:
            self.passport_number = normalize_digits(self.passport_number)

        if (
            self.birth_date
            and self.passport_issue_date
            and self.birth_date > self.passport_issue_date
        ):
            raise ValidationError(
                {
                    'passport_issue_date': (
                        'Дата выдачи паспорта не '
                        'может быть раньше даты рождения.'
                    ),
                },
            )

    class Meta:
        verbose_name = 'паспортные данные'
        verbose_name_plural = 'паспортные данные'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Паспортные данные: {self.legal_profile.user.username}'
