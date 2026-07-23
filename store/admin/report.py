"""Модуль админки для модели Report.

Содержит настройку интерфейса Django Admin для посылок.
"""

from django.contrib import admin

from store.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Администрирование отчетов."""

    list_display = (
        'id',
        'artist',
        'period_type',
        'period_start',
        'period_end',
        'status',
        'gross_amount',
        'commission_amount',
        'payout_amount',
        'created_at',
    )
    list_filter = (
        'status',
        'period_type',
        'created_at',
    )
    search_fields = (
        'artist__name',
        'artist__user__email',
    )
    readonly_fields = (
        'orders_count',
        'items_count',
        'gross_amount',
        'discount_amount',
        'delivery_amount',
        'commission_amount',
        'payout_amount',
        'report_file',
        'created_at',
        'updated_at',
    )
    ordering = (
        '-period_end',
        '-created_at',
    )
