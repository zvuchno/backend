from django.db import models

from .abstract import TimestampModel
from users.constants import (
    INN_COMPANY_MAX_LENGTH,
    NAME_FIELD_MAX_LENGTH,
    OGRN_MAX_LENGTH,
)
from users.querysets import LegalDataQuerySet
from users.validators.legal import (
    normalize_digits,
    validate_company_inn,
    validate_ogrn,
)


class ArtistCompanyData(TimestampModel):
    """Данные юридического лица артиста."""

    objects = LegalDataQuerySet.as_manager()

    legal_profile = models.OneToOneField(
        'users.ArtistLegalProfile',
        on_delete=models.CASCADE,
        related_name='company_data',
        verbose_name='Юридический профиль',
    )

    company_name = models.CharField(
        'Наименование получателя',
        max_length=NAME_FIELD_MAX_LENGTH,
        blank=True,
    )

    inn = models.CharField(
        'ИНН',
        max_length=INN_COMPANY_MAX_LENGTH,
        blank=True,
        validators=[validate_company_inn],
    )

    ogrn = models.CharField(
        'ОГРН',
        max_length=OGRN_MAX_LENGTH,
        blank=True,
        validators=[validate_ogrn],
    )

    def clean(self):
        super().clean()

        if self.inn:
            self.inn = normalize_digits(self.inn)

        if self.ogrn:
            self.ogrn = normalize_digits(self.ogrn)

    def save(self, *args, **kwargs):
        """Сохраняет объект после полной валидации модели."""
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'данные юридического лица'
        verbose_name_plural = 'данные юридических лиц'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Данные юр лица: {self.legal_profile.user.username}'
