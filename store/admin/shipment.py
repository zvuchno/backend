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
    search_fields = (
        'artist__user__email',
        'order__order_number',
        'tracking_number',
    )
    search_help_text = (
        'Поиск по email арстиста, номеру заказа, трек-номеру отправления',
    )
    readonly_fields = (
        'order',
        'artist',
        'state',
        'cdek_uuid',
        'tracking_number',
        'weight',
        'estimated_delivery_cost',
        'created_at',
        'updated_at',
    )
    list_select_related = ('order', 'artist__user')
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
                    'estimated_delivery_cost',
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

    def has_add_permission(self, request):
        """Запрещает ручное создание через кнопку 'Добавить'."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление через кнопку 'Удалить'."""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещает ручное сохранение через кнопки 'Сохранить'."""
        return False
