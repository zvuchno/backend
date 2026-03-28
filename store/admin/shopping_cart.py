"""Модуль админки для модели ShoppingCart.

Содержит настройку интерфейса Django Admin для модели корзины пользователя.
"""

from django.contrib import admin
from django.utils.html import format_html

from store.models import CartItem, ShoppingCart


class CartItemInline(admin.TabularInline):
    """Fff."""

    model = CartItem
    extra = 1
    fields = ('product', 'quantity', 'get_price')
    readonly_fields = ('get_price',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

    @admin.display(description='Цена (ед.)')
    def get_price(self, obj):
        """Проходим цепочку: CartItem -> ProductVariant -> Product -> price."""
        try:
            # 1. Проверяем связь с Вариантом
            variant = obj.product
            # 2. Проверяем связь Варианта с основным Продуктом
            product_main = variant.product
            return f'{product_main.price} руб.'
        except AttributeError:
            # Если какая-то из связей еще не выбрана или пуста
            return '—'


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Ffff."""

    list_display = ('user',)
    search_fields = ('user', 'user__email')
    fields = ('user', 'total_sum_display')
    readonly_fields = ('total_sum_display',)
    autocomplete_fields = ('user',)
    actions = ('create_order_from_cart',)
    inlines = (CartItemInline,)

    def total_sum_display(self, obj):
        """Отображает общую сумму корзины."""
        if obj is None or not obj.pk:
            return format_html(
                '<div id="id_items_total" class="readonly">0,00</div>',
            )

        total = sum(
            (item.product.price if item.product else 0) * item.quantity
            for item in obj.items.all()
        )
        formatted = f'{total:,.2f}'.replace(',', ' ')
        return format_html(
            '<div id="id_items_total" class="readonly">{}</div>',
            formatted,
        )

    total_sum_display.short_description = 'Сумма (руб.)'
