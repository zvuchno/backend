"""Модуль админки для модели Promocode.

Содержит настройку интерфейса Django Admin для модели промокодов.
"""

from django.contrib import admin

from store.models import Promocode


@admin.register(Promocode)
class PromocodeAdmin(admin.ModelAdmin):
    """Админка для модели промокодов."""

    list_display = (
        'code',
        'owner',
        'discount_type',
        'discount_value',
        'display_is_available',
        'is_active',
    )
    list_editable = ('is_active',)
    autocomplete_fields = ('owner',)
    search_fields = ('code', 'owner__email', 'owner__username')
    list_select_related = ('owner',)
    list_filter = ('discount_type', 'is_enabled', 'is_active')
    readonly_fields = (
        'created_at',
        'updated_at',
        'used_count',
        'display_is_available',
    )
    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'owner',
                    'discount_type',
                    'code',
                    'discount_value',
                    'description',
                    'is_enabled',
                    'is_active',
                    'display_is_available',
                ),
            },
        ),
        (
            'Лимиты',
            {
                'fields': (
                    'usage_limit',
                    'used_count',
                ),
            },
        ),
        (
            'Сроки действия',
            {
                'fields': (
                    'start_at',
                    'end_at',
                ),
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
    )

    @admin.display(
        boolean=True,
        description='Действующий',
    )
    def display_is_available(self, obj):
        return obj.is_available
