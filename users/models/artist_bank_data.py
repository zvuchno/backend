"""Модель банковских данных артиста."""

from django.db import models

from common.fields import (
    EncryptedCharField,
)

from .abstract import TimestampModel
from users.constants import (
    ACCOUNT_NUMBER_MAX_LENGTH,
    BANK_NAME_MAX_LENGTH,
    BIK_MAX_LENGTH,
    INN_MAX_LENGTH,
)
from users.querysets import LegalDataQuerySet
from users.validators import (
    normalize_digits,
    validate_bik,
    validate_checking_account,
    validate_correspondent_account,
    validate_inn,
)


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

    inn = EncryptedCharField(
        'ИНН',
        max_length=INN_MAX_LENGTH,
        blank=True,
        validators=[validate_inn],
    )

    bank_name = models.CharField(
        'Название банка',
        max_length=BANK_NAME_MAX_LENGTH,
        blank=True,
    )
    bik = models.CharField(
        'БИК',
        max_length=BIK_MAX_LENGTH,
        blank=True,
        validators=[validate_bik],
    )
    correspondent_account = EncryptedCharField(
        'Корреспондентский счет',
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        validators=[validate_correspondent_account],
    )
    checking_account = EncryptedCharField(
        'Расчетный счет',
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        validators=[validate_checking_account],
    )

    def save(self, *args, **kwargs):
        """Сохраняет объект после полной валидации модели."""
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        """Нормализует поля банковских реквизитов."""
        super().clean()

        if self.bik:
            self.bik = normalize_digits(self.bik)
        if self.inn:
            self.inn = normalize_digits(self.inn)
        if self.correspondent_account:
            self.correspondent_account = normalize_digits(
                self.correspondent_account,
            )
        if self.checking_account:
            self.checking_account = normalize_digits(self.checking_account)

    class Meta:
        verbose_name = 'банковские данные'
        verbose_name_plural = 'банковские данные'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Банковские данные: {self.legal_profile.user.username}'
