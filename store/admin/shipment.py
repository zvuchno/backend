"""Модуль админки для модели Shipment.

Содержит настройку интерфейса Django Admin для посылок.
"""

from django.contrib import admin

from store.models import Shipment


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    """Админка типов мерча."""

    list_display = (
        'order',
        'artist',
        'state',
        'tracking_number',
        'updated_at',
    )
    list_filter = (
        'state',
        'created_at',
    )
    search_fields = ('artist', 'order', 'tracking_number')
    search_help_text = (
        'Поиск по арстисту, номера заказа, трек-номеру отправления',
    )
    readonly_fields = (
        'order',
        'artist',
        'state',
        'cdek_uuid',
        'tracking_number',
        'weight',
        'created_at',
        'updated_at',
    )
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'order',
                    'artist',
                    'state',
                    'cdek_uuid',
                    'tracking_number',
                    'weight',
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
