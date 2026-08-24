"""Админка выплат."""

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from common.utils.money import format_money

from store.admin.forms import MoneyForm
from store.models import Payout


class PayoutAdminForm(MoneyForm):
    """Форма выплаты с форматированием суммы."""

    money_fields = ['amount']


class ReportMonthFilter(admin.SimpleListFilter):
    """Фильтр выплат по отчетному месяцу."""

    title = 'Отчетный месяц'
    parameter_name = 'report_month'

    def lookups(self, request, model_admin):
        periods = (
            model_admin
            .get_queryset(request)
            .values_list(
                'report__period_start',
                flat=True,
            )
            .distinct()
            .order_by('-report__period_start')
        )

        return [
            (
                period.strftime('%Y-%m'),
                period.strftime('%m.%Y'),
            )
            for period in periods
            if period
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset

        year, month = map(int, value.split('-'))

        return queryset.filter(
            report__period_start__year=year,
            report__period_start__month=month,
        )


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    """Администрирование ручных выплат."""

    form = PayoutAdminForm

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
    list_display_links = (
        'id',
        'get_payout_recipient',
    )
    list_filter = (
        'status',
        ReportMonthFilter,
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
        'payout_recipient_link',
        'payout_recipient_email',
        'get_period',
        'get_report_amount',
        'payout_recipient_details',
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
                    'payout_recipient_link',
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
            'Реквизиты получателя',
            {
                'fields': ('payout_recipient_details',),
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
        description='Получатель выплаты',
        ordering='payout_recipient__email',
    )
    def get_payout_recipient(self, obj):
        """Возвращает имя получателя выплаты."""
        profile = getattr(
            obj.payout_recipient,
            'artist_profile',
            None,
        )

        return (
            profile.name
            if profile and profile.name
            else obj.payout_recipient.email
        )

    @admin.display(description='Получатель выплаты')
    def payout_recipient_link(self, obj):
        """Возвращает ссылку на профиль получателя выплаты."""
        profile = getattr(
            obj.payout_recipient,
            'artist_profile',
            None,
        )

        if profile is None:
            return obj.payout_recipient.email

        url = reverse(
            'admin:users_artistprofile_change',
            args=(profile.pk,),
        )

        return format_html(
            '<a href="{}">{}</a>',
            url,
            profile.name,
        )

    @admin.display(
        description='Email',
        ordering='payout_recipient__email',
    )
    def payout_recipient_email(self, obj):
        """Возвращает email получателя."""
        return obj.payout_recipient.email

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

    @admin.display(description='Реквизиты')
    def payout_recipient_details(self, obj):
        """Возвращает реквизиты получателя выплаты."""
        details = get_payout_recipient_details(
            obj.payout_recipient,
        )

        if not details:
            return '—'

        return format_html_join(
            '',
            '{}: <strong>{}</strong><br>',
            details.items(),
        )

    @admin.action(
        description='Отметить выбранные выплаты как выплаченные',
    )
    def mark_as_paid(self, request, queryset):
        """Фиксирует выбранные выплаты как выплаченные."""
        updated = queryset.exclude(
            status=Payout.Status.PAID,
        ).update(
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

    def save_model(self, request, obj, form, change):
        """Синхронизирует дату выплаты со статусом."""
        if obj.status == Payout.Status.PAID and obj.paid_at is None:
            obj.paid_at = timezone.now()

        super().save_model(
            request,
            obj,
            form,
            change,
        )


def get_payout_recipient_details(user) -> dict[str, str]:
    """Возвращает реквизиты получателя выплаты для отображения."""
    legal_profile = getattr(
        user,
        'legal_profile',
        None,
    )

    if legal_profile is None:
        return {}

    details = {
        'Форма': legal_profile.get_recipient_type_display(),
    }

    if (
        legal_profile.recipient_type
        == legal_profile.RecipientType.LEGAL_ENTITY
    ):
        company = getattr(
            legal_profile,
            'company_data',
            None,
        )

        details.update({
            'Наименование': (getattr(company, 'company_name', '') or '—'),
            'Адрес': (getattr(company, 'company_address', '') or '—'),
            'ИНН': getattr(company, 'inn', '') or '—',
            'ОГРН': getattr(company, 'ogrn', '') or '—',
        })
    else:
        identity = getattr(
            legal_profile,
            'identity_data',
            None,
        )

        full_name = ' '.join(
            part
            for part in (
                getattr(identity, 'last_name', ''),
                getattr(identity, 'first_name', ''),
                getattr(identity, 'middle_name', ''),
            )
            if part
        )

        details.update({
            'ФИО': full_name or '—',
            'Дата рождения': (getattr(identity, 'birth_date', '') or '—'),
            'Адрес регистрации': (
                getattr(identity, 'registration_address', '') or '—'
            ),
            'ИНН': getattr(identity, 'inn', '') or '—',
            'Серия паспорта': (
                getattr(identity, 'passport_series', '') or '—'
            ),
            'Номер паспорта': (
                getattr(identity, 'passport_number', '') or '—'
            ),
            'Кем выдан': (getattr(identity, 'passport_issued_by', '') or '—'),
            'Дата выдачи': (
                getattr(identity, 'passport_issue_date', '') or '—'
            ),
        })

    bank = getattr(
        legal_profile,
        'bank_data',
        None,
    )

    details.update({
        'Банк': getattr(bank, 'bank_name', '') or '—',
        'БИК': getattr(bank, 'bik', '') or '—',
        'Корреспондентский счет': (
            getattr(bank, 'correspondent_account', '') or '—'
        ),
        'Расчетный счет': (getattr(bank, 'checking_account', '') or '—'),
    })

    return details
