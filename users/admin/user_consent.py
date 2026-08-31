"""Модуль админки для модели юридических согласий.

Содержит настройку интерфейса Django Admin для модели ConsentDocument.
"""

from django.contrib import admin, messages
from rest_framework.exceptions import PermissionDenied

from users.models import UserConsent
from users.services import ConsentService


class ConsentStatusFilter(admin.SimpleListFilter):
    """Фильтр согласий по статусу отзыва."""

    title = 'статус согласия'
    parameter_name = 'consent_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Действующие'),
            ('revoked', 'Отозванные'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(revoked_at__isnull=True)

        if self.value() == 'revoked':
            return queryset.filter(revoked_at__isnull=False)

        return queryset


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    """Админка модели UserConsent."""

    actions = ('revoke_selected_consents',)

    list_display = (
        'email',
        'is_authorized',
        'document',
        'consent_status',
        'accepted_at',
        'revoked_at',
    )
    readonly_fields = (
        'email',
        'user',
        'created_at',
        'updated_at',
        'consent_status',
        'accepted_at',
        'revoked_at',
        'document',
        'order',
        'artist',
        'user_agent',
        'ip_address',
    )
    list_filter = (
        ConsentStatusFilter,
        'document__document_type',
        'accepted_at',
        'revoked_at',
    )
    search_fields = ('email', 'user__email')
    fieldsets = (
        (
            'Пользователь',
            {
                'fields': (
                    'email',
                    'user',
                ),
            },
        ),
        (
            'Согласие',
            {
                'fields': (
                    'document',
                    'consent_status',
                    'accepted_at',
                    'revoked_at',
                ),
            },
        ),
        ('Контекст', {'fields': ('order', 'artist')}),
        (
            'Дополнительно',
            {
                'fields': (
                    'ip_address',
                    'user_agent',
                ),
            },
        ),
    )

    @admin.display(description='Авторизован', boolean=True)
    def is_authorized(self, obj):
        """Проверяет, привязано ли согласие к профилю пользователя."""
        return obj.user_id is not None

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'document')

    def has_add_permission(self, request):
        """Запрещает ручное создание согласий через кнопку 'Добавить'."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление согласий через кнопку 'Удалить'."""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещает ручное редактирование."""
        return False

    @admin.action(description='Отозвать выбранные согласия')
    def revoke_selected_consents(self, request, queryset):
        """Отзывает выбранные типы согласий пользователя."""
        if not request.user.has_perm('users.change_userconsent'):
            raise PermissionDenied

        revoked_count = 0
        processed = set()

        for consent in queryset.select_related('document', 'user'):
            subject = (
                ('user', consent.user_id)
                if consent.user_id
                else ('email', consent.email)
            )
            key = (
                subject,
                consent.document.document_type,
            )

            if key in processed:
                continue

            processed.add(key)

            revoked_count += ConsentService.revoke(
                document_type=consent.document.document_type,
                user=consent.user,
                email=consent.email,
            )

        self.message_user(
            request,
            f'Отозвано согласий: {revoked_count}.',
            level=messages.SUCCESS,
        )

    @admin.display(description='Статус')
    def consent_status(self, obj):
        """Возвращает статус согласия."""
        return 'Отозвано' if obj.is_revoked else 'Действует'
