"""Модуль админки для модели Delivery.

Содержит настройку интерфейса Django Admin для модели доставок.
"""

from django.contrib import admin

from store.models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    """Админка вариантов доставки."""

    list_display = (
        'name',
        'description',
        'price',
        'is_active',
    )
    list_editable = (
        'price',
        'is_active',
    )
    readonly_fields = ('created_at', 'updated_at')
    fields = (
        'name',
        'description',
        'price',
        'is_active',
        'created_at',
        'updated_at',
    )
    search_fields = ('name',)
    list_filter = ('name',)
    ordering = ('name',)
