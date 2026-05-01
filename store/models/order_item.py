"""Модель позиции в заказе покупателя."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from store.constants import (
    MAX_COMMENT_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)


class OrderItem(models.Model):
    """Товар в заказе."""

    order = models.ForeignKey(
        'store.Order',
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заказ',
    )
    product_variant = models.ForeignKey(
        'store.ProductVariant',
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name='Продукт',
    )
    comment = models.TextField(
        'Комментарий артисту',
        max_length=MAX_COMMENT_LENGTH,
        blank=True,
        default='',
    )

    # Поля для математики и отчетов
    price_at_purchase = models.DecimalField(
        'Цена на момент покупки, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
        help_text='Цена за единицу товара на момент оформления заказа',
    )
    unit_price = models.DecimalField(
        'Цена с донатом за ед., руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
        help_text='Цена с донатом, руб.',
    )
    quantity = models.PositiveIntegerField(
        'Количество',
        default=1,
        validators=[MinValueValidator(1)],
    )
    promocode_discount = models.DecimalField(
        'Скидка по промокоду, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
        help_text='Скидка по промокоду продавца, руб.',
    )

    # Snapshot {name, variant_name, artist..}
    product_info = models.JSONField('Данные о товаре (snapshot)', default=dict)

    @property
    def donation(self) -> Decimal:
        """Разница между уплаченным и номиналом."""
        return max(
            (self.unit_price - self.price_at_purchase) * self.quantity,
            ZERO_MONEY,
        )

    @property
    def line_total(self) -> Decimal:
        """Сумма за всю позицию."""
        return max(
            (self.unit_price * self.quantity - self.promocode_discount),
            ZERO_MONEY,
        )

    class Meta:
        verbose_name = 'товар в заказе'
        verbose_name_plural = 'товары в заказе'
        constraints = [
            models.UniqueConstraint(
                fields=('order', 'product_variant'),
                name='unique_product_variant_in_order',
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=F('price_at_purchase')),
                name='unit_price_gte_price_at_purchase',
            ),
            models.CheckConstraint(
                condition=Q(
                    promocode_discount__lte=F('unit_price') * F('quantity'),
                ),
                name='discount_not_exceed_total',
            ),
        ]

    def __str__(self):
        name = self.product_info.get('name', 'Товар')
        return f'{name} (x{self.quantity})'
