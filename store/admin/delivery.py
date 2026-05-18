"""Модуль админки для модели Delivery.

Содержит настройку интерфейса Django Admin для модели доставок.
"""

from django.contrib import admin

from common.utils.money import format_money

from .forms import MoneyForm
from store.models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    """Админка вариантов доставки."""

    form = MoneyForm

    list_display = (
        'name',
        'description',
        'delivery_type',
        'display_price',
        'is_active',
    )
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'name',
                    'delivery_type',
                    'description',
                    'price',
                    'is_active',
                ),
            },
        ),
        (
            'Системная информация',
            {
                'fields': (
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )

    search_fields = ('name',)
    list_filter = ('name',)
    ordering = ('name',)

    @admin.display(description='Цена', ordering='price')
    def display_price(self, obj):
        return format_money(obj.price)
