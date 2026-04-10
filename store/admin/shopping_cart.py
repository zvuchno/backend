"""Модуль админки для модели ShoppingCart.

Содержит настройку интерфейса Django Admin для модели корзины пользователя.
TODO: Устранить N+1 в геттерах @property сумм
"""

from django.contrib import admin
from django.db import models
from django.forms import Textarea

from store.models import CartItem, ProductVariant, ShoppingCart


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Регистрация ProductVariant для autocomplete_fields."""

    search_fields = (
        'sku',
        'characteristic',
        'product__track__name',
        'product__album__name',
        'product__merch__name',
    )

    def has_module_permission(self, request):
        """Скрываем из главного меню админки."""
        return False


class CartItemInline(admin.TabularInline):
    """Инлайн отображения позиций в корзине."""

    model = CartItem
    extra = 0
    fields = (
        'product_variant',
        'get_allow_overpay',
        'quantity',
        'get_price',
        'custom_price',
        'get_item_sum',
        'comment',
    )
    autocomplete_fields = ('product_variant',)
    readonly_fields = ('get_allow_overpay', 'get_price', 'get_item_sum')
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 30})},
    }

    @admin.display(description='Сумма, руб.')
    def get_item_sum(self, obj):
        """Отображает результат property item_sum."""
        if obj and obj.pk:
            return obj.item_sum
        return '-'

    def get_queryset(self, request):
        """Оптимизирует запрос, подтягивая всю цепочку связей."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'product_variant__product',
                'product_variant__product__track',
                'product_variant__product__album',
                'product_variant__product__merch',
            )
        )

    @admin.display(description='Цена (руб.)')
    def get_price(self, obj):
        """Проходим цепочку: CartItem -> ProductVariant -> Product -> price."""
        if obj.product_variant and obj.product_variant.product:
            return obj.product_variant.product.price
        return None

    @admin.display(description='Разрешена переплата', boolean=True)
    def get_allow_overpay(self, obj):
        """Возвращает флаг разрешения переплаты из связанного продукта."""
        if obj.product_variant and obj.product_variant.product:
            return obj.product_variant.product.allow_overpay
        return None


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Админка модели ShoppingCart с вложенными позициями."""

    list_display = ('user', 'get_subtotal_sum', 'get_discounted_subtotal')
    search_fields = ('user__username', 'user__email')
    fields = ('user', 'get_subtotal_sum', 'get_discounted_subtotal')
    autocomplete_fields = ('user',)
    readonly_fields = ('get_subtotal_sum', 'get_discounted_subtotal')
    inlines = (CartItemInline,)

    @admin.display(description='Сумма (руб.)')
    def get_subtotal_sum(self, obj):
        return f'{obj.subtotal:,.2f}'.replace(',', ' ')

    @admin.display(description='Итого (руб.)')
    def get_discounted_subtotal(self, obj):
        return f'{obj.discounted_subtotal:,.2f}'.replace(',', ' ')

    def get_queryset(self, request):
        # Подгружаем юзера сразу для всего списка
        return super().get_queryset(request).select_related('user')
