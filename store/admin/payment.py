"""Модуль админки для модели Payment.

Содержит настройку интерфейса Django Admin для модели приема платежей.
"""

from django.contrib import admin
from django.utils.html import format_html

from store.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Админка для модели платежей."""

    list_display = (
        'payment_info',
        'amount',
        'status',
        'provider_payment_id',
        'created_at',
    )
    list_select_related = ('order',)
    list_filter = ('status', 'created_at')
    search_fields = ('order__order_number', 'provider_payment_id')
    readonly_fields = (
        'status',
        'order',
        'amount',
        'provider_payment_id',
        'created_at',
        'updated_at',
        'error_code',
    )
    ordering = ('-created_at',)

    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'status',
                    'order',
                    'order_link',
                    'amount',
                    'provider_payment_id',
                    'error_code',
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

    def payment_info(self, obj):
        return f'Платеж №{obj.id} по заказу №{obj.order.order_number}'

    payment_info.short_description = 'Информация о платеже'

    def status(self, obj):
        colors = {
            'succeeded': 'green',
            'canceled': 'orange',
            'failed': 'red',
        }
        color = colors.get(obj.status)
        return format_html(
            '<b style="color: {};">{}</b>',
            color,
            obj.status.upper(),
        )

    status.short_description = 'Статус'

    def has_add_permission(self, request):
        """Запрещает ручное создание заказов через кнопку 'Добавить'."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление заказов через кнопку 'Удалить'."""
        return False
