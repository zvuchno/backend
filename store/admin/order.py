"""Модуль админки для модели Order.

Содержит настройку интерфейса Django Admin для модели заказа покупателя.
"""

from django.contrib import admin

from store.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Инлайн отображения позиций в корзине."""

    model = OrderItem
    extra = 0
    readonly_fields = (
        'product_variant',
        'product_info',
        'get_allow_overpay',
        'quantity',
        'price_at_purchase',
        'get_donation',
        'unit_price',
        'get_line_total',
        'comment',
    )
    can_delete = False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Донат')
    def get_donation(self, obj):
        if obj and obj.pk:
            return obj.donation
        return '-'

    @admin.display(description='Итого')
    def get_line_total(self, obj):
        if obj and obj.pk:
            return obj.line_total
        return '-'

    @admin.display(description='Разрешена переплата', boolean=True)
    def get_allow_overpay(self, obj):
        """Берет флаг разрешения переплаты из сохраненного снапшота."""
        if obj.product_info and isinstance(obj.product_info, dict):
            return obj.product_info.get('allow_overpay', False)
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Админка модели Order с вложенными позициями."""

    list_display = (
        'order_number',
        'user',
        'status',
        'delivery',
        'grand_total',
    )
    list_editable = ('status',)
    readonly_fields = (
        'order_number',
        'user',
        'items_total',
        'delivery_price',
        'grand_total',
        'comment',
    )
    search_fields = (
        'order_number',
        'user__email',
        'user__username',
        'full_name',
        'email',
        'phone',
    )
    list_filter = (
        'status',
        'created_at',
    )
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'order_number',
                    'user',
                    'status',
                    'comment',
                ),
            },
        ),
        (
            'Контакты',
            {
                'fields': (
                    'full_name',
                    'email',
                    'phone',
                ),
            },
        ),
        (
            'Доставка',
            {
                'fields': (
                    'delivery',
                    'city',
                    'street',
                    'house',
                    'apartment',
                ),
            },
        ),
        (
            'Итоги',
            {
                'fields': (
                    'items_total',
                    'delivery_price',
                    'grand_total',
                ),
            },
        ),
    )
    inlines = (OrderItemInline,)
