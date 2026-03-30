"""Модель корзины покупателя."""

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum

from store.models import ProductVariant

User = get_user_model()


class ShoppingCart(models.Model):
    """Корзина пользователя."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cart',
        verbose_name='Покупатель',
    )
    product_variant = models.ManyToManyField(
        ProductVariant,
        through='CartItem',
        related_name='carts',
        verbose_name='Варианты продукта',
    )

    @property
    def subtotal(self):
        """Считает сумму товаров без учета скидки.

        Выполняет агрегацию на стороне базы данных: перемножает количество
        каждого товара на его актуальную цену и суммирует результаты.
        """
        result = self.items.aggregate(
            total=Sum(F('quantity') * F('product_variant__product__price')),
        )
        return result['total'] or 0

    @property
    def discounted_subtotal(self):
        """Сумма корзины с учетом промокода."""
        pass

    class Meta:
        verbose_name = 'корзина'
        verbose_name_plural = 'корзины'

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
        verbose_name='Продукт',
    )
    quantity = models.PositiveIntegerField(
        'Количество',
        default=1,
        validators=[MinValueValidator(1)],
    )

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
