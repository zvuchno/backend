"""Модуль админки слушателя."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from users.models import ListenerProfile


@admin.register(ListenerProfile)
class ListenerProfileAdmin(admin.ModelAdmin):
    """Админка профиля слушателя."""

    readonly_fields = (
        'account_phone',
        'account_username',
        'user_link',
        'created_at',
        'updated_at',
    )

    list_display = (
        'id',
        'user',
        'full_name',
        'is_active',
        'created_at',
    )
    list_display_links = ('id', 'user', 'full_name')
    list_filter = (
        'is_active',
        'created_at',
    )
    search_fields = (
        'full_name',
        'user__phone',
        'user__username',
        'user__email',
    )
    ordering = ('-created_at',)

    fieldsets = [
        (
            'Пользователь',
            {
                'fields': (
                    'user_link',
                    'account_username',
                    'account_phone',
                ),
            },
        ),
        (
            'Основная информация',
            {
                'fields': ('full_name',),
            },
        ),
        (
            'Статус',
            {
                'fields': ('is_active',),
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
    ]

    def has_add_permission(self, request):
        """Запрещает ручное создание профиля слушателя."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление объектов через админку."""
        return False

    def get_actions(self, request):
        """Убирает массовое удаление из списка действий."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    @admin.display(description='Телефон учетной записи')
    def account_phone(self, obj):
        if not obj or not obj.user_id:
            return '—'
        return obj.user.phone or '—'

    @admin.display(description='Учетная запись')
    def user_link(self, obj):
        url = reverse('admin:users_coreuser_change', args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)

    @admin.display(description='Имя пользователя')
    def account_username(self, obj):
        return obj.user.username or '—'
