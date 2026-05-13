"""Модель промокода."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models

User = get_user_model()


class Promocode(models.Model):
    """Промокод, создаваемый артистом. Действует на все его товары."""

    code_validator = RegexValidator(
        regex=r'^[A-Z0-9]+$',
        message=(
            'Код может содержать только заглавные латинские буквы и цифры.'
        ),
    )

    artist = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='promocodes',
        verbose_name='Артист',
    )
    code = models.CharField(
        'Код промокода',
        max_length=32,
        unique=True,
        validators=[code_validator],
    )
    description = models.TextField(
        'Описание',
        blank=True,
        default='',
    )
    discount_percent = models.PositiveSmallIntegerField(
        'Размер скидки, %',
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    usage_limit = models.PositiveIntegerField(
        'Количество использований',
        null=True,
        blank=True,
        help_text='Пусто = неограничено',
    )
    used_count = models.PositiveIntegerField(
        'Использовано раз',
        default=0,
    )
    valid_from = models.DateField('Действует с')
    valid_until = models.DateField('Действует по')
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                check=models.Q(valid_until__gte=models.F('valid_from')),
                name='promocode_valid_until_gte_valid_from',
            ),
            models.CheckConstraint(
                check=models.Q(discount_percent__gte=1)
                & models.Q(discount_percent__lte=100),
                name='promocode_discount_percent_range',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.code} ({self.discount_percent}%)'

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.upper()
        if (
            self.valid_from
            and self.valid_until
            and self.valid_until < self.valid_from
        ):
            raise ValidationError({
                'valid_until': (
                    'Дата окончания не может быть раньше даты начала.'
                ),
            })
