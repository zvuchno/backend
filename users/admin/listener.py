"""Модуль админки слушателя.

TODO добавить Имя
"""

from django.contrib import admin

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
    search_fields = (
        'full_name',
        'user__phone',
        'user__username',
        'user__email',
    )
    ordering = ('-created_at',)
    autocomplete_fields = ('user', 'full_name')
