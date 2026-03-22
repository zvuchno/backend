"""Модуль описания торговых предложений (SKU) для интернет-магазина."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)
from store.models import Carrier, Product


class ProductVariant(models.Model):
    """Конкретная единица товара (SKU), доступная для покупки.

    Представляет конкретную конфигурацию продукта с ценой,
    остатком на складе и типом носителя.
    На уровне БД гарантирует уникальность носителя
    в рамках одного продукта.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name='Вариант продукта',
    )
    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.PROTECT,
        related_name='variants',
        verbose_name='Носитель',
        null=True,
        blank=True,
    )
    sku = models.CharField(
        'SKU',
        max_length=MAX_CHAR_LENGTH,
        unique=True,
    )
    price = models.DecimalField(
        'Цена',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Цена, руб.',
    )
    stock = models.PositiveIntegerField(
        'Доступно',
        default=0,
        help_text='Наличие на складе',
    )
    characteristic = models.JSONField(
        'Свойства',
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = 'вариант продукта'
        verbose_name_plural = 'варианты продукта'
        ordering = ('id',)
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'carrier'],
                name='unique_product_carrier',
            ),
        ]

    def __str__(self):
        return f'SKU: {self.sku} [{self.product.product_type}]'
