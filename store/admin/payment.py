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
        'id',
        'payment_info',
        'amount',
        'colored_status',
        'provider_payment_id',
        'paid_at',
    )
    list_display_links = ('id', 'payment_info')
    list_select_related = ('order',)
    list_filter = ('status', 'paid_at')
    search_fields = ('order__order_number', 'provider_payment_id')
    readonly_fields = (
        'colored_status',
        'order',
        'amount',
        'provider_payment_id',
        'created_at',
        'updated_at',
        'paid_at',
        'error_code',
    )
    ordering = ('-created_at',)

    def get_fieldsets(self, request, obj=None):
        fields = [
            'colored_status',
            'order',
            'amount',
            'provider_payment_id',
            'paid_at',
        ]

        if obj and obj.error_code:
            fields.insert(1, 'error_code')

        return (
            (
                'Основные данные',
                {
                    'fields': tuple(fields),
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

    @admin.display(description='Информация о платеже')
    def payment_info(self, obj):
        return f'Оплата по заказу №{obj.order.order_number}'

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

    def has_add_permission(self, request):
        """Запрещает ручное создание через кнопку 'Добавить'."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление через кнопку 'Удалить'."""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещает ручное сохранение через кнопки 'Сохранить'."""
        return False
