"""Модель юридических и банковских данных артиста."""

from django.db import models

from .abstract import TimestampModel
from users.constants import (
    ACCOUNT_NUMBER_MAX_LENGTH,
    ADDRESS_FIELD_MAX_LENGTH,
    BANK_NAME_MAX_LENGTH,
    BIK_MAX_LENGTH,
    INN_MAX_LENGTH,
    NAME_FIELD_MAX_LENGTH,
    PASSPORT_ISSUED_BY_MAX_LENGTH,
    PASSPORT_NUMBER_MAX_LENGTH,
    PASSPORT_SERIES_MAX_LENGTH,
    TAXATION_FORM_MAX_LENGTH,
)


class ArtistLegalProfile(TimestampModel):
    """Закрытые юридические и платежные данные артиста.

    Не предназначены для публичного отображения.
    Используются для выплат, отчетности и договорной работы.
    """

    class TaxationForm(models.TextChoices):
        SELF_EMPLOYED = 'self_employed', 'Самозанятый'
        INDIVIDUAL_ENTREPRENEUR = 'individual_entrepreneur', 'ИП'
        INDIVIDUAL = 'individual', 'Физическое лицо'
        LEGAL_ENTITY = 'legal_entity', 'Юридическое лицо'

    artist = models.OneToOneField(
        'users.ArtistProfile',
        on_delete=models.CASCADE,
        related_name='legal_profile',
        verbose_name='Профиль артиста',
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

    inn = models.CharField(
        'ИНН',
        max_length=INN_MAX_LENGTH,
        blank=True,
        default='',
    )

    bank_name = models.CharField(
        'Название банка',
        max_length=BANK_NAME_MAX_LENGTH,
        blank=True,
        default='',
    )
    bik = models.CharField(
        'БИК',
        max_length=BIK_MAX_LENGTH,
        blank=True,
        default='',
    )
    correspondent_account = models.CharField(
        'Корреспондентский счет',
        max_length=20,
        blank=True,
        default='',
    )
    checking_account = models.CharField(
        'Расчетный счет',
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        default='',
    )

    taxation_form = models.CharField(
        'Форма налогообложения',
        max_length=TAXATION_FORM_MAX_LENGTH,
        choices=TaxationForm.choices,
        blank=True,
        default='',
    )

    is_verified = models.BooleanField(
        'Проверено',
        default=False,
        help_text='Данные проверены вручную.',
    )

    class Meta:
        verbose_name = 'юридические данные артиста'
        verbose_name_plural = 'юридические данные артистов'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Юридические данные: {self.artist.name}'
