"""Модуль админки для модели Carrier.

Содержит настройку интерфейса Django Admin для модели музыкальных носителей.
"""

from django.contrib import admin

from store.models import Carrier


@admin.register(Carrier)
class GenreAdmin(admin.ModelAdmin):
    """Админка для модели Carrier."""

    list_display = (
        'name',
        'slug',
        'is_active',
    )
    search_fields = ('name',)
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    ordering = ('name', 'is_active')
