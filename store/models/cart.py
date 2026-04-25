"""Модели корзины покупок."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
    When,
)
from django.db.models.functions import Coalesce

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
)
from users.models.abstract import TimestampModel


class CartQuerySet(models.QuerySet):
    """Кверисет для работы с корзинами покупок.."""

    def with_subtotal(self):
        """Аннотирует каждую корзину общей стоимостью всех её позиций.

        Выполняет расчет на уровне базы данных одним запросом.
        Логика расчета цены за единицу совпадает с CartItem.with_prices:
        - unit_price_expr: выбор актуальной цены за единицу товара.
        - line_total_expr: умножение unit_price на количество (quantity).
        - _subtotal: сумма всех line_total для данной корзины.
        Возвращает:
            QuerySet с дополнительным полем '_subtotal' (Decimal)
        """
        # Вычисляем цену за единицу (unit_price)
        unit_price_expr = Case(
            When(
                items__product_variant__product__allow_overpay=True,
                then=Coalesce(
                    F('items__price_with_donation'),
                    F('items__product_variant__product__price'),
                ),
            ),
            default=F('items__product_variant__product__price'),
            output_field=DecimalField(
                max_digits=MAX_PRICE_DIGITS,
                decimal_places=MONEY_INTERNAL_PRECISION,
            ),
        )

        # Вычисляем сумму строки (line_total)
        line_total_expr = ExpressionWrapper(
            unit_price_expr * F('items__quantity'),
            output_field=DecimalField(
                max_digits=MAX_PRICE_DIGITS,
                decimal_places=MONEY_INTERNAL_PRECISION,
            ),
        )

        # Финальная аннотация
        return self.annotate(
            _subtotal=Coalesce(
                Sum(line_total_expr),
                Decimal('0.0000'),
                output_field=DecimalField(
                    max_digits=MAX_PRICE_DIGITS,
                    decimal_places=MONEY_INTERNAL_PRECISION,
                ),
            ),
        ).select_related('user')


class Cart(TimestampModel):
    """Корзина пользователя."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
        verbose_name='Покупатель',
    )
    session_key = models.CharField(
        'Ключ сессии',
        max_length=MAX_CHAR_LENGTH,
        null=True,
        blank=True,
    )
    objects = CartQuerySet.as_manager()

    @property
    def subtotal(self):
        """Всегда возвращает правильную сумму."""
        # Проверяем, нет ли уже готового значения из БД
        if hasattr(self, '_subtotal'):
            return self._subtotal
        # Если нет, делаем агрегацию Fallback — одним запросом
        return self.items.with_prices().aggregate(
            total=Coalesce(Sum('_line_total'), Decimal('0.0000')),
        )['total']

    @property
    def discount_promocode(self):
        """Сумма скидки по промокоду."""
        return Decimal('0.0000')  # TODO: Пока не реализованы промокоды

    @property
    def total(self):
        """Сумма корзины с учетом промокода."""
        return self.subtotal  # TODO: Пока не реализованы промокоды, доделать

    def clean(self):
        super().clean()
        if not self.user and not self.session_key:
            raise ValidationError(
                'Корзина должна иметь владельца (пользователя или сессию).',
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'корзина'
        verbose_name_plural = 'корзины'
        constraints = [
            models.UniqueConstraint(
                fields=['session_key'],
                name='unique_session_cart',
                condition=models.Q(session_key__isnull=False),
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False)
                    | models.Q(session_key__isnull=False)
                ),
                name='cart_has_owner',
            ),
        ]

    def __str__(self):
        if self.user:
            return f'Корзина {self.user}'
        return f'Анонимная корзина [id: ...{str(self.session_key)[:16]}]'
