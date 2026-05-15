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
        'order',
        'artist',
        'user_agent',
        'ip_address',
    )
    list_filter = ('accepted_at',)
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
                    'accepted_at',
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

    @admin.display(description='Зарегистрирован', boolean=True)
    def is_registered(self, obj):
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
