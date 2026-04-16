"""Модель позиций в заказе покупателя."""

from django.db import models

from store.constants import (
    MAX_COMMENT_LENGTH,
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)


class OrderItem(models.Model):
    """Товар в заказе."""

    order = models.ForeignKey(
        'store.Order',
        on_delete=models.CASCADE,
        related_name='items',
    )
    product_variant = models.ForeignKey(
        'store.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items',
        verbose_name='Продукт',
    )
    comment = models.TextField(
        'Комментарий к заказу',
        max_length=MAX_COMMENT_LENGTH,
        blank=True,
        null=True,
        help_text='Сообщение для артиста',
    )

    # Поля для математики и отчетов
    price_at_purchase = models.DecimalField(
        'Цена на момент покупки, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        help_text='Цена за единицу товара на момент оформления заказа',
    )
    unit_price = models.DecimalField(
        'Фактическая оплата за ед., руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        help_text='Цена с донатом, руб.',
    )
    quantity = models.PositiveIntegerField(
        'Количество',
        default=1,
    )

    # Snapshot {name, variant_name, artist..}
    product_info = models.JSONField('Данные о товаре (snapshot)', default=dict)

    @property
    def donation(self):
        """Разница между уплаченным и номиналом."""
        return self.unit_price - self.price_at_purchase

    @property
    def line_total(self):
        """Сумма за всю позицию."""
        return self.unit_price * self.quantity

    class Meta:
        verbose_name = 'товар в заказе'
        verbose_name_plural = 'товары в заказе'
        constraints = [
            models.UniqueConstraint(
                fields=('order', 'product_variant'),
                name='unique_product_variant_in_order',
            ),
        ]

    def __str__(self):
        return f'{self.product_info.get("name", "Товар")} (x{self.quantity})'
