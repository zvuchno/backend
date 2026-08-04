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
        'period_start',
        'period_end',
        'status',
        'get_sales_amount',
        'updated_at',
    )
    list_filter = (
        'status',
        'updated_at',
    )
    search_fields = (
        'artist__name',
        'artist__user__email',
    )
    readonly_fields = (
        'status',
        'artist',
        'period_start',
        'period_end',
        'get_sales_amount',
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
        description='Продано товаров на сумму (руб.)',
        ordering='sales_amount',
    )
    def get_sales_amount(self, obj):
        """Сумма продаж."""
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

    @admin.display(description='Стоимость доставок (руб.)')
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
                    'period_start',
                    'period_end',
                    'get_sales_amount',
                    'get_commission_amount',
                    'get_delivery_amount',
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

    def has_add_permission(self, request):
        """Запрещает ручное создание через кнопку 'Добавить'."""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещает ручное сохранение через кнопки 'Сохранить'."""
        return False
