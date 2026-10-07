"""Модуль админки для модели Bonus.

Содержит настройку интерфейса Django Admin для модели бонусов.
"""

from django.contrib import admin

from store.models import Bonus


@admin.register(Bonus)
class BonusAdmin(admin.ModelAdmin):
    """Админка для модели бонусов."""

    list_display = (
        'name',
        'artist',
        'album',
        'updated_at',
        'is_active',
    )
    list_editable = ('is_active',)
    search_fields = ('name',)
    list_filter = ('is_active',)
    readonly_fields = (
        'artist',
        'album',
        'bonus_file',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'name',
                    'artist',
                    'album',
                    'bonus_file',
                    'description',
                    'is_active',
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

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'album__artist__user',
            )
        )

    @admin.display(description='Артист')
    def artist(self, obj):
        return f'{obj.album.artist.user.email} - {obj.album.artist}'

    def has_add_permission(self, request):
        """Запрещает ручное создание через кнопку 'Добавить'."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление через кнопку 'Удалить'."""
        return False
