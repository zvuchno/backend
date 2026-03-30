"""Модуль админки для модели ShoppingCart.

Содержит настройку интерфейса Django Admin для модели корзины пользователя.
"""

from django.contrib import admin

from store.models import CartItem, ProductVariant, ShoppingCart


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Регистрация CartItem для autocomplete_fields."""

    search_fields = (
        'sku',
        'characteristic',
        # Если продукт — это трек:
        'product__track__name',
        # Если продукт — это альбом:
        'product__album__name',
        # Если продукт — это мерч:
        'product__merch__name',
    )

    def has_module_permission(self, request):
        """Скрываем из главного меню админки."""
        return False


class CartItemInline(admin.TabularInline):
    """Инлайн отображения позиций в корзине."""

    model = CartItem
    extra = 0
    fields = ('product_variant', 'quantity', 'get_price')
    autocomplete_fields = ('product_variant',)
    readonly_fields = ('get_price',)

    def get_queryset(self, request):
        """Оптимизирует запрос, подтягивая всю цепочку связей."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'product_variant__product',  # Достаем вариант и продукт
                'product_variant__product__track',  # Достаем трек
                'product_variant__product__album',  # Достаем альбом
                'product_variant__product__merch',  # Достаем мерч
            )
        )

    @admin.display(description='Цена (руб.)')
    def get_price(self, obj):
        """Проходим цепочку: CartItem -> ProductVariant -> Product -> price."""
        if obj.product_variant and obj.product_variant.product:
            return obj.product_variant.product.price
        return None


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Админка модели ShoppingCart с вложенными позициями."""

    list_display = ('user', 'get_total_sum')
    search_fields = ('user__username', 'user__email')
    fields = ('user', 'get_total_sum')
    autocomplete_fields = ('user',)
    readonly_fields = ('get_total_sum',)
    inlines = (CartItemInline,)

    @admin.display(description='Сумма (руб.)')
    def get_total_sum(self, obj):
        return f'{obj.subtotal:,.2f}'.replace(',', ' ')

    def get_queryset(self, request):
        # Подгружаем юзера сразу для всего списка
        return super().get_queryset(request).select_related('user')
