from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()


class CartItem(models.Model):
    """Товар в корзине."""

    cart = models.ForeignKey(
        'store.ShoppingCart',
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'store.ProductVariant',
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
                fields=('cart', 'product'),
                name='unique_product_in_cart',
            ),
        ]

    def __str__(self):
        return f'{self.product} × {self.quantity}'
