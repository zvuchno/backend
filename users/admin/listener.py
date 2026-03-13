"""Модуль админки слушателя.

TODO добавить Имя
"""

from django.contrib import admin

from users.models import ListenerProfile


@admin.register(ListenerProfile)
class ListenerProfileAdmin(admin.ModelAdmin):
    """Админка профиля слушателя"""
    list_display = (
        'id',
        'user',
        'phone',
        'is_active',
        'created_at',
    )
    list_filter = (
        'is_active',
        'created_at',
    )
    search_fields = (
        'phone',
        'user__username',
        'user__email',
    )
    ordering = ('-created_at',)
    autocomplete_fields = ('user',)
