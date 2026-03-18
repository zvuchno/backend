"""Модуль админки для модели Kind.

Содержит настройку интерфейса Django Admin для типов мерча.
"""

from django.contrib import admin

from store.models import Kind


@admin.register(Kind)
class KindAdmin(admin.ModelAdmin):
    """Админка типов мерча."""

    list_display = (
        'name',
        'slug',
    )
    list_filter = (
        'created_at',
        'is_active',
    )
    search_fields = ('name',)
    search_help_text = 'Поиск по имени'
