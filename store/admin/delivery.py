"""Модуль админки для модели Delivery.

Содержит настройку интерфейса Django Admin для модели доставок.
"""

from django.contrib import admin

from .forms import MoneyForm
from store.models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    """Админка вариантов доставки."""

    form = MoneyForm

    list_display = (
        'name',
        'delivery_type',
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
