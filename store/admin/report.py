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
        'get_payout_recipient',
        'payout_recipient_email',
        'period_start',
        'period_end',
        'status',
        'get_sales_amount',
        'get_commission_amount',
        'get_payout_amount',
        'updated_at',
    )
    list_filter = (
        'status',
        'updated_at',
    )
    search_fields = (
        'payout_recipient__email',
        'payout_recipient__artist_profile__name',
    )
    readonly_fields = (
        'status',
        'get_payout_recipient',
        'period_start',
        'period_end',
        'get_sales_amount',
        'get_donation_amount',
        'get_discount_amount',
        'get_commission_amount',
        'get_payout_amount',
        'report_file_link',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)
    list_display_links = ('id', 'get_payout_recipient')
    list_select_related = (
        'payout_recipient',
        'payout_recipient__artist_profile',
    )

    @admin.display(
        description='Продано (руб.)',
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

    @admin.display(
        description='Добровольные доплаты (руб.)',
        ordering='donation_amount',
    )
    def get_donation_amount(self, obj):
        """Добровольные доплаты."""
        return format_money(obj.donation_amount)

    @admin.display(description='Скидки по промокоду (руб.)')
    def get_discount_amount(self, obj):
        """Скидки по промокоду."""
        return format_money(obj.discount_amount)

    @admin.display(description='Файл отчета')
    def report_file_link(self, obj):
        """Ссылка на PDF отчета."""
        if not obj.report_file:
            return '—'

        filename = (
            f'Отчет {obj.payout_recipient.email} '
            f'{obj.period_start:%d.%m.%Y}-{obj.period_end:%d.%m.%Y}'
        )

        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.report_file.url,
            filename,
        )

    @admin.display(
        description='Получатель выплаты',
        ordering='payout_recipient__email',
    )
    def get_payout_recipient(self, obj):
        legal_profile = getattr(
            obj.payout_recipient,
            'legal_profile',
            None,
        )

        if legal_profile:
            recipient_type = legal_profile.recipient_type

            if recipient_type == legal_profile.RecipientType.LEGAL_ENTITY:
                company_data = getattr(
                    legal_profile,
                    'company_data',
                    None,
                )
                if company_data and company_data.company_name:
                    return company_data.company_name

            identity_data = getattr(
                legal_profile,
                'identity_data',
                None,
            )
            if identity_data:
                full_name = ' '.join(
                    part
                    for part in (
                        identity_data.last_name,
                        identity_data.first_name,
                        identity_data.middle_name,
                    )
                    if part
                )
                if full_name:
                    return full_name

        profile = getattr(
            obj.payout_recipient,
            'artist_profile',
            None,
        )
        if profile and profile.name:
            return profile.name

        return obj.payout_recipient.email

    @admin.display(
        description='Email',
        ordering='payout_recipient__email',
    )
    def payout_recipient_email(self, obj):
        return obj.payout_recipient.email

    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'status',
                    'get_payout_recipient',
                    'payout_recipient_email',
                    'period_start',
                    'period_end',
                    'get_sales_amount',
                    'get_donation_amount',
                    'get_discount_amount',
                    'get_commission_amount',
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
