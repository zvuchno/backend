"""Модуль админки для модели Genre.

Содержит настройку интерфейса Django Admin для модели жанров музыки.
"""

from django.contrib import admin

from store.models import Genre


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    """Админка для модели Genre."""

    list_display = (
        'name',
        'slug',
        'is_active',
    )
    search_fields = ('name',)
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    ordering = ('name', 'is_active')
    fieldsets = (
        ('Основная информация', {'fields': ('name', 'slug', 'is_active')}),
    )
