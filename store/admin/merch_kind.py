"""Модуль админки для модели Kind.

Содержит настройку интерфейса Django Admin для типов мерча.
"""

from django.contrib import admin

from store.models import MerchKind


@admin.register(MerchKind)
class MerchKindAdmin(admin.ModelAdmin):
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
    fieldsets = (
        ('Основная информация', {'fields': ('name', 'slug', 'is_active')}),
    )
