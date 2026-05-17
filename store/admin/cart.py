"""Модуль админки для модели Cart.

Содержит настройку интерфейса Django Admin для модели корзины пользователя.
"""

from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.utils.html import format_html

from common.utils.money import format_money

from .forms import MoneyForm
from store.models import Cart, CartItem, ProductVariant


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Регистрация ProductVariant для autocomplete_fields."""

    search_fields = (
        'sku',
        'property_value',
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
    form = MoneyForm
    extra = 0
    fields = (
        'product_variant',
        'get_allow_overpay',
        'quantity',
        'get_price',
        'price_with_donation',
        'get_line_total',
        'comment',
    )
    autocomplete_fields = ('product_variant',)
    readonly_fields = ('get_allow_overpay', 'get_price', 'get_line_total')
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 30})},
    }

    @admin.display(description='Сумма, руб.')
    def get_line_total(self, obj):
        """Отображает результат property line_total."""
        if obj and obj.pk:
            return format_money(obj.line_total)
        return '-'

    def get_queryset(self, request):
        """Оптимизирует запрос, подтягивая всю цепочку связей."""
        return (
            super()
            .get_queryset(request)
            .with_prices()
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
            return format_money(obj.product_variant.product.price)
        return None

    @admin.display(description='Разрешена переплата', boolean=True)
    def get_allow_overpay(self, obj):
        """Возвращает флаг разрешения переплаты из связанного продукта."""
        if obj.product_variant and obj.product_variant.product:
            return obj.product_variant.product.allow_overpay
        return None

    def get_formset(self, request, obj=None, **kwargs):
        """Отключаем кнопки управления связанным объектом."""
        formset = super().get_formset(request, obj, **kwargs)
        widget = formset.form.base_fields['product_variant'].widget
        widget.can_add_related = False
        widget.can_change_related = False
        widget.can_view_related = False
        return formset


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Админка модели Cart с вложенными позициями."""

    list_display = ('get_user', 'get_subtotal_sum', 'get_total')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user',)
    readonly_fields = (
        'user',
        'get_subtotal_sum',
        'get_total',
        'created_at',
        'updated_at',
    )
    inlines = (CartItemInline,)
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': ('user', 'get_subtotal_sum', 'get_total'),
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

    @admin.display(description='Покупатель', ordering='user')
    def get_user(self, obj):
        if obj.user:
            return obj.user
        return format_html(
            '<span style="color: #C0C0C0; '
            'font-style: italic;">Сессия:</span> [...{}]',
            str(obj.session_key)[:16],
        )

    @admin.display(description='Сумма (руб.)', ordering='_subtotal')
    def get_subtotal_sum(self, obj):
        return format_money(obj.subtotal)

    @admin.display(description='Итого (руб.)')
    def get_total(self, obj):
        return format_money(obj.total)

    def get_queryset(self, request):
        return super().get_queryset(request).with_subtotal()

    def has_add_permission(self, request):
        """Запрещает ручное создание заказов через кнопку 'Добавить'."""
        return False
