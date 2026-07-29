"""Модуль админки для модели Report.

Содержит настройку интерфейса Django Admin для отчетов.
"""

from django.contrib import admin
from django.utils.html import format_html

from common.utils.money import format_money

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
        'get_sales_amount',
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
        'status',
        'artist',
        'period_type',
        'period_start',
        'period_end',
        'orders_count',
        'items_count',
        'get_sales_amount',
        'get_donation_amount',
        'get_discount_amount',
        'get_delivery_amount',
        'get_commission_amount',
        'get_payout_amount',
        'report_file_link',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)
    list_display_links = ('id', 'artist')
    list_select_related = (
        'artist',
        'artist__user',
    )

    @admin.display(
        description='Валовая выручка (руб.)',
        ordering='sales_amount',
    )
    def get_sales_amount(self, obj):
        """Валовая выручка за период."""
        return format_money(obj.sales_amount)

    @admin.display(description='Комиссия (руб.)', ordering='commission_amount')
    def get_commission_amount(self, obj):
        """Комиссия платформы ."""
        return format_money(obj.commission_amount)

    @admin.display(
        description='Сумма к выплате (руб.)',
        ordering='payout_amount',
    )
    def get_payout_amount(self, obj):
        """Сумма к выплате."""
        return format_money(obj.payout_amount)

    @admin.display(
        description='Донаты (руб.)',
        ordering='donation_amount',
    )
    def get_donation_amount(self, obj):
        """Сумма донатов."""
        return format_money(obj.donation_amount)

    @admin.display(description='Скидки по промокоду (в т.ч) (руб.)')
    def get_discount_amount(self, obj):
        """Скидка по промокоду."""
        return format_money(obj.discount_amount)

    @admin.display(description='Стоимость доставок (в т.ч) (руб.)')
    def get_delivery_amount(self, obj):
        """Стоимость доставки."""
        return format_money(obj.delivery_amount)

    @admin.display(description='Файл отчета')
    def report_file_link(self, obj):
        """Ссылка на PDF отчета."""
        if not obj.report_file:
            return '—'

        filename = (
            f'Отчет {obj.artist.name} '
            f'{obj.period_start:%d.%m.%Y}-{obj.period_end:%d.%m.%Y}'
        )

        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.report_file.url,
            filename,
        )

    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'status',
                    'artist',
                    'period_type',
                    'period_start',
                    'period_end',
                    'orders_count',
                    'items_count',
                    'get_donation_amount',
                    'get_discount_amount',
                    'get_delivery_amount',
                    'get_commission_amount',
                    'get_sales_amount',
                    'get_payout_amount',
                ),
            },
        ),
        (
            'Файл отчета',
            {
                'fields': ('report_file_link',),
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
