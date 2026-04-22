"""Модель банковских данных артиста."""

from django.core.exceptions import ValidationError
from django.db import models

from .abstract import TimestampModel
from users.constants import (
    ACCOUNT_NUMBER_MAX_LENGTH,
    BANK_NAME_MAX_LENGTH,
    BIK_MAX_LENGTH,
    INN_MAX_LENGTH,
)
from users.querysets import LegalDataQuerySet


class ArtistBankData(TimestampModel):
    """Банковские данные артиста.

    Хранит ИНН и реквизиты банковского счета, используемые
    для выплат артисту.
    """

    objects = LegalDataQuerySet.as_manager()

    legal_profile = models.OneToOneField(
        'users.ArtistLegalProfile',
        on_delete=models.CASCADE,
        related_name='bank_data',
        verbose_name='Юридический профиль',
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
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        default='',
    )
    checking_account = models.CharField(
        'Расчетный счет',
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        default='',
    )

    def clean(self):
        """Проверяет формат банковских реквизитов."""
        errors = {}

        if self.inn and not self.inn.isdigit():
            errors['inn'] = 'ИНН должен содержать только цифры.'

        if self.inn and len(self.inn) not in (10, 12):
            errors['inn'] = 'ИНН должен содержать 10 или 12 цифр.'

        if self.bik and (not self.bik.isdigit() or len(self.bik) != 9):
            errors['bik'] = 'БИК должен содержать 9 цифр.'

        if self.correspondent_account and (
            not self.correspondent_account.isdigit()
            or len(self.correspondent_account) != 20
        ):
            errors['correspondent_account'] = (
                'Корреспондентский счет должен содержать 20 цифр.'
            )

        if self.checking_account and (
            not self.checking_account.isdigit()
            or len(self.checking_account) != 20
        ):
            errors['checking_account'] = (
                'Расчетный счет должен содержать 20 цифр.'
            )

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = 'банковские данные'
        verbose_name_plural = 'банковские данные'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Банковские данные: {self.legal_profile.user.username}'
