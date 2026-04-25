"""Модуль админки для модели юридических согласий.

Содержит настройку интерфейса Django Admin для модели ConsentDocument.
"""

from django.contrib import admin

from users.models import UserConsent


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    """Админка модели UserConsent."""

    list_display = (
        'email',
        'is_registered',
        'document',
        'accepted_at',
    )
    readonly_fields = (
        'email',
        'user',
        'created_at',
        'updated_at',
        'accepted_at',
        'document',
        'user_agent',
        'ip_address',
    )
    list_filter = ('accepted_at',)
    search_fields = ('email', 'user__email', 'document')
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
                    'accepted_at',
                ),
            },
        ),
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

    @admin.display(description='Зарегистрирован', boolean=True)
    def is_registered(self, obj):
        """Проверяет, привязано ли согласие к профилю пользователя."""
        return obj.user_id is not None
