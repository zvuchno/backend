"""Модуль админки юридических данных артиста."""

from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils.html import format_html

from users.models import (
    ArtistBankData,
    ArtistCompanyData,
    ArtistIdentityData,
    ArtistLegalProfile,
)

VERIFICATION_MODELS = {
    'identity_data': ArtistIdentityData,
    'bank_data': ArtistBankData,
    'company_data': ArtistCompanyData,
}


class ArtistIdentityDataInline(admin.StackedInline):
    """Инлайн паспортных данных артиста."""

    model = ArtistIdentityData
    can_delete = False
    extra = 0
    max_num = 1
    fields = (
        'last_name',
        'first_name',
        'middle_name',
        'birth_date',
        'registration_address',
        'passport_series',
        'passport_number',
        'passport_issued_by',
        'passport_issue_date',
        'inn',
        'created_at',
        'updated_at',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('legal_profile')


class ArtistBankDataInline(admin.StackedInline):
    """Инлайн банковских данных артиста."""

    model = ArtistBankData
    can_delete = False
    extra = 0
    max_num = 1
    fields = (
        'bank_name',
        'bik',
        'correspondent_account',
        'checking_account',
        'created_at',
        'updated_at',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('legal_profile')


class ArtistCompanyDataInline(admin.StackedInline):
    """Инлайн данных юридического лица."""

    model = ArtistCompanyData
    can_delete = False
    extra = 0
    max_num = 1
    fields = (
        'company_name',
        'company_address',
        'inn',
        'ogrn',
        'created_at',
        'updated_at',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('legal_profile')


class VerificationReadinessFilter(admin.SimpleListFilter):
    """Фильтр по готовности юридического профиля к проверке."""

    title = 'готов к проверке'
    parameter_name = 'verification_readiness'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да'),
            ('no', 'Нет'),
        )

    def queryset(self, request, queryset):
        """Фильтрует профили по готовности к ручной проверке.

        Важно: условие повторяет бизнес-правило
        ArtistLegalProfile.is_ready_for_verification на уровне SQL.
        При изменении обязательных полей проверки необходимо обновить
        и этот фильтр.
        """
        ready_queryset = queryset.filter(
            bank_data__bik__gt='',
            bank_data__checking_account__gt='',
        ).filter(
            models.Q(
                recipient_type__in=(
                    ArtistLegalProfile.RecipientType.SELF_EMPLOYED,
                    ArtistLegalProfile.RecipientType.INDIVIDUAL_ENTREPRENEUR,
                ),
                identity_data__last_name__gt='',
                identity_data__first_name__gt='',
                identity_data__birth_date__isnull=False,
                identity_data__registration_address__gt='',
                identity_data__passport_series__gt='',
                identity_data__passport_number__gt='',
                identity_data__passport_issued_by__gt='',
                identity_data__passport_issue_date__isnull=False,
                identity_data__inn__gt='',
            )
            | models.Q(
                recipient_type=ArtistLegalProfile.RecipientType.LEGAL_ENTITY,
                company_data__company_name__gt='',
                company_data__company_address__gt='',
                company_data__inn__gt='',
                company_data__ogrn__gt='',
            ),
        )

        if self.value() == 'yes':
            return ready_queryset

        if self.value() == 'no':
            return queryset.exclude(pk__in=ready_queryset.values('pk'))

        return queryset


@admin.register(ArtistLegalProfile)
class ArtistLegalProfileAdmin(admin.ModelAdmin):
    """Админка юридического профиля артиста."""

    inlines = (
        ArtistIdentityDataInline,
        ArtistBankDataInline,
        ArtistCompanyDataInline,
    )

    list_display = (
        'id',
        'user',
        'artist_name',
        'email',
        'recipient_type',
        'verification_readiness',
        'is_verified',
        'updated_at',
    )
    list_display_links = ('id', 'user')
    list_filter = (
        'recipient_type',
        VerificationReadinessFilter,
        'is_verified',
        'updated_at',
        'created_at',
    )
    search_fields = (
        'user__email',
        'user__username',
        'user__phone',
        'email',
        'phone',
        'user__artist_profile__name',
        'company_data__company_name',
    )
    ordering = ('-updated_at',)

    fieldsets = (
        (
            'Пользователь',
            {
                'fields': (
                    'user',
                    'artist_link',
                ),
            },
        ),
        (
            'Контакты для юридических документов',
            {
                'fields': (
                    'email',
                    'phone',
                ),
            },
        ),
        (
            'Юридический статус',
            {
                'fields': (
                    'recipient_type',
                    'verification_readiness',
                    'verification_missing_fields',
                    'is_verified',
                    'comment',
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

    autocomplete_fields = ('user',)

    @admin.display(description='Артист')
    def artist_name(self, obj):
        """Возвращает имя артиста."""
        artist = getattr(obj.user, 'artist_profile', None)
        if artist:
            return artist.name
        return '—'

    @admin.display(description='Профиль артиста')
    def artist_link(self, obj):
        """Возвращает ссылку на профиль артиста."""
        artist = getattr(obj.user, 'artist_profile', None)
        if not artist:
            return '—'

        url = reverse('admin:users_artistprofile_change', args=[artist.pk])
        return format_html('<a href="{}">{}</a>', url, artist.name)

    @admin.display(
        description='Готов к проверке',
        boolean=True,
    )
    def verification_readiness(self, obj):
        if not obj:
            return False
        return obj.is_ready_for_verification

    @admin.display(description='Не заполнено для проверки')
    def verification_missing_fields(self, obj):
        """Возвращает незаполненные обязательные данные."""
        if not obj:
            return '—'

        missing_fields = obj.get_verification_missing_fields()

        if not missing_fields:
            return '—'

        return ', '.join(
            str(self._get_verification_field_label(field))
            for field in missing_fields
        )

    def get_queryset(self, request):
        """Оптимизирует запросы списка юридических профилей."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'user',
                'user__artist_profile',
                'identity_data',
                'bank_data',
                'company_data',
            )
        )

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление юридических профилей через админку."""
        return False

    def get_actions(self, request):
        """Убирает массовое удаление из списка действий."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        """Возвращает поля только для чтения."""
        readonly_fields = [
            'artist_link',
            'created_at',
            'updated_at',
            'verification_readiness',
            'verification_missing_fields',
        ]

        if obj:
            readonly_fields.append('user')

        return readonly_fields

    def _get_verification_field_label(self, field_name) -> str:
        """Возвращает название обязательного поля для отображения."""
        if '.' not in field_name:
            return ArtistLegalProfile._meta.get_field(field_name).verbose_name

        prefix, related_field = field_name.split('.', 1)
        model = VERIFICATION_MODELS[prefix]

        return model._meta.get_field(related_field).verbose_name

    def save_related(self, request, form, formsets, change):
        """Сбрасывает подтверждение при неполных юридических данных."""
        super().save_related(request, form, formsets, change)

        obj = form.instance

        if obj.is_verified and not obj.is_ready_for_verification:
            obj.is_verified = False
            obj.save(update_fields=('is_verified',))
