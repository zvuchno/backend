"""Модуль админки для модели Category.

Содержит настройку интерфейса Django Admin для категорий.
"""

from django.contrib import admin

from store.models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Админка категорий."""

    list_display = (
        'name',
        'slug',
    )
    list_filter = ('created_at', 'is_active')
    search_fields = ('name',)
    search_help_text = 'Поиск по имени'
