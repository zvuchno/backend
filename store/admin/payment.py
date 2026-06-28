"""Модуль админки для модели Payment.

Содержит настройку интерфейса Django Admin для модели приема платежей.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from store.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Админка для модели платежей."""

    list_display = (
        'id',
        'order_link',
        'order',
        'amount',
        'status',
        'provider_payment_id',
        'created_at',
    )
    list_select_related = ('order',)
    list_filter = ('status', 'created_at')
    search_fields = ('order__order_number', 'provider_payment_id')
    readonly_fields = (
        'order',
        'order_link',
        'amount',
        'provider_payment_id',
        'created_at',
        'updated_at',
        'idempotency_key',
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

    def order_link(self, obj):
        url = reverse('admin:store_order_change', args=[obj.order.id])
        return format_html(
            '<a href="{}">Заказ №{}</a>',
            url,
            obj.order.order_number,
        )

    order_link.short_description = 'Перейти к заказу'

    def has_add_permission(self, request):
        """Запрещает ручное создание заказов через кнопку 'Добавить'."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление заказов через кнопку 'Удалить'."""
        return False
