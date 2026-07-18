"""Модуль админки для модели Order.

Содержит настройку интерфейса Django Admin для модели заказа покупателя.
"""

from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from common.utils.money import format_money

from .hooks import handle_order_status_change
from store.exceptions import NotEnoughStock
from store.models import Order, OrderItem, Payment, Shipment


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


class PaymentInline(admin.TabularInline):
    """Инлайн отображения платежей по заказу."""

    model = Payment
    extra = 0
    fields = (
        'created_at',
        'colored_status',
        'provider_payment_id',
        'amount',
        'error_code',
    )
    readonly_fields = fields
    can_delete = False

    @admin.display(description='Статус')
    def colored_status(self, obj):
        colors = {
            'pending': '#0d6efd',
            'succeeded': '#28a745',
            'canceled': '#daa024',
            'failed': '#dc3545',
        }

        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status),
            obj.get_status_display(),
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class ShipmentInline(admin.TabularInline):
    """Инлайн отображения отправлений по заказу."""

    model = Shipment
    extra = 0
    fields = (
        'artist',
        'cdek_uuid',
        'state',
        'tracking_number',
        'weight',
        'display_estimated_delivery_cost',
    )
    readonly_fields = fields
    can_delete = False

    @admin.display(description='Расчетная стоимость доставки артиста (руб.)')
    def display_estimated_delivery_cost(self, obj):
        return format_money(obj.estimated_delivery_cost)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Админка модели Order с вложенными позициями."""

    list_display = (
        'order_number',
        'created_at',
        'user',
        'status',
        'delivery',
        'is_paid',
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
        'cdek_city_code',
        'display_total',
        'promocode',
        'created_at',
        'updated_at',
        'reserved_until',
        'delivery_calculation',
        'pickup_point',
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
                    'reserved_until',
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
                    'pickup_point',
                    'display_address',
                    'cdek_city_code',
                    'delivery_calculation',
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
    inlines = (OrderItemInline, PaymentInline, ShipmentInline)

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

    @admin.display(description='Оплачен', boolean=True)
    def is_paid(self, obj):
        """Проверяет, есть ли у заказа успешно завершенный платеж."""
        return obj.payments.filter(status='succeeded').exists()

    def save_model(self, request, obj, form, change):
        if not change:
            super().save_model(request, obj, form, change)
            return

        old_status = Order.objects.get(pk=obj.pk).status

        try:
            with transaction.atomic():
                super().save_model(request, obj, form, change)
                obj.refresh_from_db()
                handle_order_status_change(obj, old_status)

        except NotEnoughStock as e:
            messages.error(request, f'Не удалось зарезервировать товары: {e}')
            return

    def get_queryset(self, request):
        # Аннотируем заказы по наличию успешного платежа
        return (
            super()
            .get_queryset(request)
            .annotate(
                has_successful_payment=Exists(
                    Payment.objects.filter(
                        order=OuterRef('pk'),
                        status='succeeded',
                    ),
                ),
            )
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
