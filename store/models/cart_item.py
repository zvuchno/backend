"""Модель позиций в корзине покупок."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, DecimalField, ExpressionWrapper, F, When
from django.db.models.functions import Coalesce

from store.constants import (
    MAX_COMMENT_LENGTH,
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)
from store.validators import validate_custom_price


class CartItemQuerySet(models.QuerySet):
    """Кверисет для позиций корзины."""

    def with_prices(self):
        """Аннотирует каждый CartItem актуальной ценой и суммой строки.

        Рассчитывает цену за единицу (_unit_price) с учетом 'allow_overpay':
           - Если переплата разрешена, приоритет у 'custom_price' (донат),
             иначе — базовая цена продукта.
           - Если переплата запрещена — всегда базовая цена.
        Рассчитывает итог строки (_line_total) как (_unit_price * quantity).

        Используется:
        - В API и админке для отображения списка товаров без N+1 запросов.
        - В методе Cart.subtotal (fallback) для расчета суммы корзины.

        Внимание: Изменения в логике этого метода должны быть синхронизированы
        с CartQuerySet.with_subtotal, который дублирует расчет для оптимизации.

        Возвращает:
            QuerySet: кверисет с аннотированными полями '_unit_price'
            и '_line_total' (тип Decimal).
        """
        return (
            self
            .select_related(
                'product_variant__product',
            )
            .annotate(
                # _unit_price — цена за единицу с учётом allow_overpay
                _unit_price=Case(
                    When(
                        product_variant__product__allow_overpay=True,
                        then=Coalesce(
                            F('custom_price'),
                            F('product_variant__product__price'),
                        ),
                    ),
                    default=F('product_variant__product__price'),
                    output_field=DecimalField(
                        max_digits=MAX_PRICE_DIGITS,
                        decimal_places=PRICE_DECIMAL_PLACES,
                    ),
                ),
            )
            .annotate(
                # _line_total — итог по строке (для агрегации и свойства)
                _line_total=ExpressionWrapper(
                    F('_unit_price') * F('quantity'),
                    output_field=DecimalField(
                        max_digits=MAX_PRICE_DIGITS,
                        decimal_places=PRICE_DECIMAL_PLACES,
                    ),
                ),
            )
        )


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
    custom_price = models.DecimalField(
        'Хочет заплатить, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
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
    objects = CartItemQuerySet.as_manager()

    @property
    def unit_price(self):
        """Актуальная цена за единицу товара (аннотация или Python)."""
        # Проверяем, нет ли уже готового значения из БД
        if hasattr(self, '_unit_price'):
            return self._unit_price
        # Fallback логика
        product = self.product_variant.product
        if product.allow_overpay and self.custom_price is not None:
            return self.custom_price
        return product.price

    @property
    def line_total(self):
        """Сумма по позиции."""
        if hasattr(self, '_line_total'):
            return self._line_total
        # Юзаем unit_price
        return self.unit_price * self.quantity

    def clean(self):
        super().clean()
        errors = validate_custom_price(
            self.product_variant.product,
            self.custom_price,
        )
        if errors:
            raise ValidationError(errors)

        product = self.product_variant.product
        if product.product_type in ['album', 'track'] and self.quantity > 1:
            raise ValidationError(
                {
                    'quantity': 'Ненормально покупать цифровые товары '
                    'в количестве больше одного. Одумайтесь.',
                },
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

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
