"""Модели корзины покупок."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, F, Sum, When
from django.db.models.functions import Coalesce

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_COMMENT_LENGTH,
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)
from store.models import ProductVariant
from store.validators import validate_custom_price
from users.models.abstract import TimestampModel


class ShoppingCart(TimestampModel):
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

    @property
    def subtotal(self):
        """Считает сумму всей корзины одним SQL-запросом.

        Если переплата разрешена: берем custom_price
        или базовую, если custom_price — NULL.
        Если переплата запрещена: базовая цена.
        """
        return self.items.aggregate(
            total=Sum(
                F('quantity')
                * Case(
                    # Если переплата разрешена
                    When(
                        product_variant__product__allow_overpay=True,
                        then=Coalesce(
                            F('custom_price'),
                            F('product_variant__product__price'),
                        ),
                    ),
                    # Если переплата запрещена
                    default=F('product_variant__product__price'),
                    output_field=models.DecimalField(),
                ),
                output_field=models.DecimalField(
                    max_digits=MAX_PRICE_DIGITS,
                    decimal_places=PRICE_DECIMAL_PLACES,
                ),
            ),
        )['total'] or Decimal('0.00')

    @property
    def discounted_subtotal(self):
        """Сумма корзины с учетом промокода."""
        return self.subtotal  # Пока не реализованы промокоды TODO: доделать

    class Meta:
        verbose_name = 'корзина'
        verbose_name_plural = 'корзины'
        constraints = [
            models.UniqueConstraint(
                fields=['session_key'],
                name='unique_session_cart',
                condition=models.Q(session_key__isnull=False),
            ),
        ]

    def __str__(self):
        return f'Корзина {self.user}'


class CartItem(models.Model):
    """Товар в корзине."""

    cart = models.ForeignKey(
        ShoppingCart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product_variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='cart_items',
        verbose_name='Продукт',
    )
    quantity = models.PositiveIntegerField(
        'Количество',
        default=1,
        validators=[MinValueValidator(1)],
    )
    custom_price = models.DecimalField(
        'Хочет заплатить, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        null=True,
        blank=True,
        default=None,
        help_text='Цена с донатом, руб.',
    )
    comment = models.TextField(
        'Комментарий к заказу',
        max_length=MAX_COMMENT_LENGTH,
        blank=True,
        null=True,
        help_text='Сообщение для артиста',
    )

    def clean(self):
        super().clean()
        errors = validate_custom_price(
            self.product_variant.product,
            self.custom_price,
        )
        if errors:
            raise ValidationError(errors)

    @property
    def item_sum(self):
        """Считает сумму строки.

        Кастомная цена или цена продукта * количество.
        Если переплата разрешена и введена кастомная цена — берем её.
        В противном случае — номинал из продукта.
        """
        product = self.product_variant.product
        if product.allow_overpay and self.custom_price:
            price = self.custom_price
        else:
            price = product.price
        return price * self.quantity

    class Meta:
        verbose_name = 'позиция в корзине'
        verbose_name_plural = 'позиции в корзине'
        constraints = [
            models.UniqueConstraint(
                fields=('cart', 'product_variant'),
                name='unique_product_variant_in_cart',
            ),
        ]

    def __str__(self):
        return f'{self.product_variant} × {self.quantity}'
