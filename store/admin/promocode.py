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
        'artist',
        'discount_type',
        'discount_value',
        'display_is_available',
        'is_active',
    )
    list_editable = ('is_active',)
    search_fields = ('code', 'artist__user__email', 'artist__user__username')
    list_select_related = ('artist',)
    list_filter = ('discount_type', 'is_enabled', 'is_active')

    def get_readonly_fields(self, request, obj=None):
        """Возвращает поля, недоступные для ручного изменения."""
        readonly_fields = (
            *super().get_readonly_fields(request, obj),
            'created_at',
            'updated_at',
            'created_by',
            'used_count',
            'display_is_available',
        )

        if obj is not None:
            readonly_fields += ('artist',)

        return readonly_fields

    autocomplete_fields = ('artist',)

    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'artist',
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
                    'created_by',
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

    def save_model(self, request, obj, form, change):
        """Сохраняет пользователя, создавшего промокод."""
        if not change and obj.created_by_id is None:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)
