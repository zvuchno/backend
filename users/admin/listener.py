"""Модуль админки слушателя.

TODO добавить Имя
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from users.models import ListenerProfile


@admin.register(ListenerProfile)
class ListenerProfileAdmin(admin.ModelAdmin):
    """Админка профиля слушателя."""

    list_display = (
        'id',
        'user',
        'full_name',
        'is_active',
        'created_at',
    )
    list_display_links = ('id', 'full_name')
    list_filter = (
        'is_active',
        'created_at',
    )
    readonly_fields = ('account_phone', 'user_link')
    search_fields = (
        'full_name',
        'user__phone',
        'user__username',
        'user__email',
    )
    ordering = ('-created_at',)
    autocomplete_fields = ('user',)

    @admin.display(description='Учетная запись')
    def user_link(self, obj):
        url = reverse('admin:users_coreuser_change', args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)

    @admin.display(description='Телефон учетной записи')
    def account_phone(self, obj):
        return obj.user.phone or '—'

    fieldsets = [
        (
            'Пользователь',
            {
                'fields': ('user', 'user_link'),
            },
        ),
        (
            'Основная информация',
            {
                'fields': ('full_name',),
            },
        ),
        (
            'Контакты',
            {
                'fields': ('account_phone',),
            },
        ),
        (
            'Статус',
            {
                'fields': ('is_active',),
            },
        ),
    ]
