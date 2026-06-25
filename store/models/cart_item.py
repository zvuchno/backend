"""Модель позиций в корзине покупок."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from store.constants import (
    MAX_COMMENT_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
)
from store.querysets import CartItemQuerySet
from store.validators import validate_price_with_donation


class CartItem(models.Model):
    """Товар в корзине."""

    cart = models.ForeignKey(
        'store.Cart',
        on_delete=models.CASCADE,
        related_name='items',
    )
    product_variant = models.ForeignKey(
        'store.ProductVariant',
        on_delete=models.CASCADE,
        related_name='cart_items',
        verbose_name='Продукт',
    )
    quantity = models.PositiveIntegerField(
        'Количество',
        default=1,
        validators=[MinValueValidator(1)],
    )
    price_with_donation = models.DecimalField(
        'Хочет заплатить, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        null=True,
        blank=True,
        help_text='Цена с донатом, руб.',
    )
    comment = models.TextField(
        'Комментарий к заказу',
        max_length=MAX_COMMENT_LENGTH,
        blank=True,
        null=True,
        help_text='Сообщение для артиста',
    )
    is_artist_subscription = models.BooleanField(
        'Согласие на рассылку артиста',
        default=False,
    )
    objects = CartItemQuerySet.as_manager()

    @property
    def unit_price(self):
        """Актуальная цена за единицу товара (аннотация или Python)."""
        # Проверяем, нет ли уже готового значения из БД
        if hasattr(self, '_unit_price'):
            return self._unit_price
        # Fallback логика
        product = self.product_variant.product
        if product.allow_overpay and self.price_with_donation is not None:
            return self.price_with_donation
        return product.price

    @property
    def base_line_total(self):
        """Исходная стоимость позиции (с донатом) до применения промокода."""
        if hasattr(self, '_line_total'):
            return self._line_total
        # Юзаем unit_price
        return self.unit_price * self.quantity

    def clean(self):
        super().clean()
        errors = validate_price_with_donation(
            self.product_variant.product,
            self.price_with_donation,
        )
        if errors:
            raise ValidationError(errors)

        product = self.product_variant.product
        if product.product_type in ['album', 'track'] and self.quantity > 1:
            raise ValidationError(
                {
                    'quantity': 'Цифровые товары можно '
                    'приобрести только в одном экземпляре.',
                },
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'позиция в корзине'
        verbose_name_plural = 'позиции в корзине'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=('cart', 'product_variant'),
                name='unique_product_variant_in_cart',
            ),
        ]

    def __str__(self):
        return f'{self.product_variant} × {self.quantity}'
