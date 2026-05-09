"""Модуль админки юридических данных артиста."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from users.models import (
    ArtistBankData,
    ArtistCompanyData,
    ArtistIdentityData,
    ArtistLegalProfile,
)


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


@admin.register(ArtistLegalProfile)
class ArtistLegalProfileAdmin(admin.ModelAdmin):
    """Админка юридического профиля артиста."""

    inlines = (
        ArtistIdentityDataInline,
        ArtistBankDataInline,
        ArtistCompanyDataInline,
    )

    readonly_fields = (
        'user',
        'artist_link',
        'created_at',
        'updated_at',
    )

    list_display = (
        'id',
        'user',
        'artist_name',
        'email',
        'recipient_type',
        'is_verified',
        'updated_at',
    )
    list_display_links = ('id', 'user')
    list_filter = (
        'recipient_type',
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

    def has_add_permission(self, request):
        """Запрещает ручное создание юридических профилей через админку."""
        return False

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
