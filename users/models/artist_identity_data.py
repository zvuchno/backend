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


class ArtistIdentityData(TimestampModel):
    """Паспортные данные артиста.

    Хранит ФИО, дату рождения, адрес регистрации и реквизиты
    документа, удостоверяющего личность. Используется для выплат,
    отчетности и юридической идентификации артиста.
    """

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
    )
    passport_number = models.CharField(
        'Номер паспорта',
        max_length=PASSPORT_NUMBER_MAX_LENGTH,
        blank=True,
        default='',
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
    )

    def clean(self):
        """Проверяет формат паспортных данных."""
        errors = {}

        if self.passport_series and not self.passport_series.isdigit():
            errors['passport_series'] = (
                'Серия паспорта должна содержать цифры.'
            )

        if self.passport_number and not self.passport_number.isdigit():
            errors['passport_number'] = (
                'Номер паспорта должен содержать цифры.'
            )

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = 'паспортные данные'
        verbose_name_plural = 'паспортные данные'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Паспортные данные: {self.legal_profile.user.username}'
