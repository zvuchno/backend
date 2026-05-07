"""Модель банковских данных артиста."""

from django.db import models

from .abstract import TimestampModel
from users.constants import (
    ACCOUNT_NUMBER_MAX_LENGTH,
    BANK_NAME_MAX_LENGTH,
    BIK_MAX_LENGTH,
)
from users.querysets import LegalDataQuerySet
from users.validators import (
    normalize_digits,
    validate_bik,
    validate_checking_account,
    validate_correspondent_account,
)


class ArtistBankData(TimestampModel):
    """Банковские данные артиста.

    Хранит реквизиты банковского счета, используемые
    для выплат артисту.
    """

    objects = LegalDataQuerySet.as_manager()

    legal_profile = models.OneToOneField(
        'users.ArtistLegalProfile',
        on_delete=models.CASCADE,
        related_name='bank_data',
        verbose_name='Юридический профиль',
    )

    bank_name = models.CharField(
        'Название банка',
        max_length=BANK_NAME_MAX_LENGTH,
        blank=True,
        null=True,
    )
    bik = models.CharField(
        'БИК',
        max_length=BIK_MAX_LENGTH,
        blank=True,
        null=True,
        validators=[validate_bik],
    )
    correspondent_account = models.CharField(
        'Корреспондентский счет',
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        null=True,
        validators=[validate_correspondent_account],
    )
    checking_account = models.CharField(
        'Расчетный счет',
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        null=True,
        validators=[validate_checking_account],
    )

    def save(self, *args, **kwargs):
        """Сохраняет объект после полной валидации модели."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Нормализует поля банковских реквизитов."""
        super().clean()

        if self.bik:
            self.bik = normalize_digits(self.bik)
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
