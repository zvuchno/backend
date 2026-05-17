"""Модель промокодов."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from store.constants import (
    DISCOUNT_VALUE_PRECISION,
    MAX_PRICE_DIGITS,
    MAX_PROMOCODE_LENGTH,
)
from store.validators import validate_promocode_format
from users.models.abstract import ActivatableModel, TimestampModel


class Promocode(ActivatableModel, TimestampModel):
    """Промокод для применения скидок в заказах.

    Поддерживает два типа скидок:
    - процентная (PERCENT)
    - фиксированная сумма (FIXED)

    Основные возможности:
    - ограничение по количеству использований;
    - контроль периода действия (start_at / end_at);
    - включение/отключение промокода (is_enabled);
    - хранение количества фактических применений;
    - привязка к артисту.
    """

    class DiscountType(models.TextChoices):
        PERCENT = 'PERCENT', 'Процент'
        FIXED = 'FIXED', 'Фиксированная (руб)'

    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.PERCENT,
        verbose_name='Тип скидки',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='promocodes',
        verbose_name='Артист',
    )
    code = models.CharField(
        'Код промокода',
        max_length=MAX_PROMOCODE_LENGTH,
        unique=True,
        validators=[validate_promocode_format],
        help_text='Только заглавные '
        'латинские буквы, цифры, дефис и подчеркивание',
    )
    description = models.TextField('Описание', blank=True, default='')
    discount_value = models.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Размер скидки',
    )

    # Лимиты
    usage_limit = models.PositiveIntegerField(
        'Макс. количество использований',
        null=True,
        blank=True,
        help_text='Пусто = неограничено',
    )
    used_count = models.PositiveIntegerField(
        'Использовано раз',
        default=0,
    )

    # Сроки действия
    start_at = models.DateTimeField(
        'Начало действия',
        null=True,
        blank=True,
    )
    end_at = models.DateTimeField(
        'Окончание действия',
        null=True,
        blank=True,
    )

    is_enabled = models.BooleanField('Включен', default=True)

    @property
    def is_available(self) -> bool:
        """Определяет, доступен ли промокод для использования в данный момент.

        Промокод считается доступным, если он активен,
        включен, текущее время входит в диапазон его действия
        и не исчерпан лимит использований.
        """
        now = timezone.now()

        is_started = self.start_at is None or self.start_at <= now
        is_not_expired = self.end_at is None or now <= self.end_at
        under_limit = (
            self.usage_limit is None or self.used_count < self.usage_limit
        )
        return (
            self.is_active
            and self.is_enabled
            and is_started
            and is_not_expired
            and under_limit
        )

    def clean(self):
        super().clean()

        if self.discount_value is not None:
            if (
                self.discount_type == self.DiscountType.PERCENT
                and self.discount_value > 100
            ):
                raise ValidationError({
                    'discount_value': 'Скидка не может быть больше 100%.',
                })

        if self.usage_limit is not None and self.used_count > self.usage_limit:
            raise ValidationError({
                'used_count': (
                    'Количество использований не может превысить лимит.'
                ),
            })

        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValidationError({
                'end_at': 'Дата окончания не может быть раньше даты начала.',
            })

    class Meta:
        verbose_name = 'промокод'
        verbose_name_plural = 'промокоды'
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=(
                    # Если даты заполнены, окончание должно быть позже начала
                    models.Q(
                        start_at__isnull=False,
                        end_at__isnull=False,
                        end_at__gt=models.F('start_at'),
                    )
                    # Пропускаем проверку, если хотя бы одной даты нет
                    | models.Q(start_at__isnull=True)
                    | models.Q(end_at__isnull=True)
                ),
                name='promocode_end_at_strictly_gt_start_at',
            ),
            models.CheckConstraint(
                condition=(
                    # Если процент — строго <= 100
                    models.Q(
                        discount_type='PERCENT',
                        discount_value__gt=0,
                        discount_value__lte=100,
                    )
                    | models.Q(discount_type='FIXED', discount_value__gt=0)
                ),
                name='promocode_discount_value_valid',
            ),
        ]

    def __str__(self):
        return (
            f'{self.code} '
            f'({self.get_discount_type_display()}: {self.discount_value})'
        )
