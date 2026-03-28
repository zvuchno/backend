"""Модель корзины покупателя."""

from django.contrib.auth import get_user_model
from django.db import models

from store.models import ProductVariant

User = get_user_model()


class ShoppingCart(models.Model):
    """Корзина пользователя."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cart',
        verbose_name='Покупатель',
    )
    products = models.ManyToManyField(
        ProductVariant,
        through='CartItem',
        related_name='carts',
        verbose_name='Варианты продукта',
    )

    class Meta:
        verbose_name = 'корзина'
        verbose_name_plural = 'корзины'

    def __str__(self):
        return f'Корзина {self.user}'
