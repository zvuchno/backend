"""Модуль админки для модели Order.

Содержит настройку интерфейса Django Admin для модели заказа покупателя.
"""

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

from common.utils.money import format_money

from store.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Инлайн отображения позиций в заказе."""

    model = OrderItem
    extra = 0
    fields = (
        'display_product_link',
        'product_info',
        'display_allow_overpay',
        'display_price_at_purchase',
        'quantity',
        'display_donation',
        'display_promocode_discount',
        'display_line_total',
        'comment',
    )
    readonly_fields = fields
    can_delete = False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Товар')
    def display_product_link(self, obj):
        """Возвращает ссылку на родительский контент через вариант продукта.

        Текст ссылки берется из строкового представления варианта. Переход
        осуществляется в админку основной сущности (Альбома, Трека или Мерча),
        к которой привязан универсальный продукт. Если ссылка не может быть
        построена, возвращается строковое представление варианта.
        """
        if not obj.product_variant:
            return obj.product_info.get('name', 'Товар (удален)')

        variant = obj.product_variant
        # Используем __str__ варианта как текст ссылки
        link_text = str(variant)
        product = getattr(variant, 'product', None)
        if product:
            content_obj = product.album or product.track or product.merch
            if content_obj:
                try:
                    url = reverse(
                        f'admin:{content_obj._meta.app_label}_'
                        f'{content_obj._meta.model_name}_change',
                        args=[content_obj.id],
                    )
                    return mark_safe(f'<a href="{url}">{link_text}</a>')
                except NoReverseMatch:
                    pass
        return link_text

    @admin.display(description='Разрешена переплата', boolean=True)
    def display_allow_overpay(self, obj):
        """Берет флаг разрешения переплаты из сохраненного снапшота."""
        if obj.product_info and isinstance(obj.product_info, dict):
            return obj.product_info.get('allow_overpay', False)
        return False

    @admin.display(description='Донат')
    def display_donation(self, obj):
        if obj and obj.pk:
            return format_money(obj.donation)
        return '-'

    @admin.display(description='Сумма руб.')
    def display_line_total(self, obj):
        if obj and obj.pk:
            return format_money(obj.line_total)
        return '-'

    @admin.display(description='Цена на момент покупки, руб.')
    def display_price_at_purchase(self, obj):
        return format_money(obj.price_at_purchase)

    @admin.display(description='Скидка по промокоду, руб.')
    def display_promocode_discount(self, obj):
        return format_money(obj.promocode_discount)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Админка модели Order с вложенными позициями."""

    list_display = (
        'order_number',
        'email',
        'is_authorized',
        'status',
        'delivery',
        'display_total',
    )
    list_editable = ('status',)
    readonly_fields = (
        'order_number',
        'user',
        'full_name',
        'email',
        'phone',
        'display_subtotal',
        'display_delivery_price',
        'display_promocode_discount',
        'delivery',
        'display_address',
        'display_total',
        'promocode',
        'created_at',
        'updated_at',
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
            'Основная информация',
            {
                'fields': (
                    'order_number',
                    'user',
                    'status',
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
                    'display_address',
                ),
            },
        ),
        (
            'Итоги',
            {
                'fields': (
                    'display_subtotal',
                    'display_promocode_discount',
                    'display_delivery_price',
                    'display_total',
                    'promocode',
                ),
            },
        ),
        (
            'Системная информация',
            {
                'classes': ('collapse',),
                'fields': (
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )
    inlines = (OrderItemInline,)

    @admin.display(description='Сумма товаров (руб.)')
    def display_subtotal(self, obj):
        return format_money(obj.subtotal)

    @admin.display(description='Стоимость доставки (руб.)')
    def display_delivery_price(self, obj):
        return format_money(obj.delivery_price)

    @admin.display(description='Сумма скидки по промокоду (руб.)')
    def display_promocode_discount(self, obj):
        return format_money(obj.promocode_discount)

    @admin.display(description='Итого (руб.)', ordering='total')
    def display_total(self, obj):
        return format_money(obj.total)

    @admin.display(description='Адрес доставки')
    def display_address(self, obj):
        parts = [
            f'г. {obj.city}' if obj.city else None,
            f'ул. {obj.street}' if obj.street else None,
            f'д. {obj.house}' if obj.house else None,
            f'кв/оф. {obj.apartment}' if obj.apartment else None,
        ]
        return ', '.join(filter(None, parts)) or '-'

    @admin.display(description='Авторизован', boolean=True)
    def is_authorized(self, obj):
        """Проверяет, привязан ли заказ к профилю пользователя."""
        return obj.user_id is not None

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                'items__product_variant__product__album',
                'items__product_variant__product__track',
                'items__product_variant__product__merch',
            )
        )

    def has_add_permission(self, request):
        """Запрещает ручное создание заказов через кнопку 'Добавить'."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление заказов через кнопку 'Удалить'."""
        return False
