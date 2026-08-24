"""Админка выплат."""

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from common.utils.money import format_money

from store.models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    """Администрирование ручных выплат."""

    list_display = (
        'id',
        'get_payout_recipient',
        'payout_recipient_email',
        'get_period',
        'get_amount',
        'status',
        'paid_at',
        'updated_at',
    )
    list_filter = (
        'status',
        'paid_at',
    )
    search_fields = (
        'payout_recipient__email',
        'payout_recipient__artist_profile__name',
    )
    list_select_related = (
        'report',
        'payout_recipient',
        'payout_recipient__artist_profile',
    )
    ordering = ('status', '-created_at')
    actions = ('mark_as_paid',)

    readonly_fields = (
        'report_link',
        'get_payout_recipient',
        'payout_recipient_profile_link',
        'payout_recipient_email',
        'get_period',
        'get_report_amount',
        'paid_at',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        (
            'Выплата',
            {
                'fields': (
                    'status',
                    'get_payout_recipient',
                    'payout_recipient_profile_link',
                    'payout_recipient_email',
                    'report_link',
                    'get_period',
                    'get_report_amount',
                    'amount',
                    'comment',
                    'paid_at',
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

    @admin.display(
        description='Получатель',
        ordering='payout_recipient__email',
    )
    def get_payout_recipient(self, obj):
        """Возвращает имя получателя выплаты."""
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
        """Возвращает email получателя."""
        return obj.payout_recipient.email

    @admin.display(description='Профиль получателя')
    def payout_recipient_profile_link(self, obj):
        """Возвращает ссылку на профиль получателя."""
        profile = getattr(
            obj.payout_recipient,
            'artist_profile',
            None,
        )
        if profile is None:
            return '—'

        url = reverse(
            'admin:users_artistprofile_change',
            args=(profile.pk,),
        )
        return format_html(
            '<a href="{}">{}</a>',
            url,
            profile.name,
        )

    @admin.display(description='Отчет')
    def report_link(self, obj):
        """Возвращает ссылку на отчет."""
        url = reverse(
            'admin:store_report_change',
            args=(obj.report_id,),
        )
        return format_html(
            '<a href="{}">Отчет #{}</a>',
            url,
            obj.report_id,
        )

    @admin.display(description='Период')
    def get_period(self, obj):
        """Возвращает отчетный период."""
        return (
            f'{obj.report.period_start:%d.%m.%Y} — '
            f'{obj.report.period_end:%d.%m.%Y}'
        )

    @admin.display(
        description='Сумма выплаты',
        ordering='amount',
    )
    def get_amount(self, obj):
        """Возвращает сумму выплаты."""
        return format_money(obj.amount)

    @admin.display(description='По отчету')
    def get_report_amount(self, obj):
        """Возвращает рассчитанную сумму отчета."""
        return format_money(obj.report.payout_amount)

    @admin.action(
        description='Отметить выбранные выплаты как выплаченные',
    )
    def mark_as_paid(self, request, queryset):
        """Фиксирует выбранные выплаты как выплаченные."""
        updated = queryset.exclude(status=Payout.Status.PAID).update(
            status=Payout.Status.PAID,
            paid_at=timezone.now(),
        )

        self.message_user(
            request,
            f'Отмечено выплаченными: {updated}.',
        )

    def has_add_permission(self, request):
        """Запрещает ручное создание выплат."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление выплат."""
        return False
