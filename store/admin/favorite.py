"""Модуль админки для модели Favorite.

Содержит настройку интерфейса Django Admin для модели Избранное.
"""

from django.contrib import admin

from store.models.favorite import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Админка модели избранного."""

    # Поля в списке записей
    list_display = (
        'get_user_info',
        'get_product_info',
        'created_at',
    )

    # Фильтры
    list_filter = (
        'created_at',
        'product_variant__product__product_type',
    )

    # Поиск по полям
    search_fields = (
        'user__username',
        'user__email',
        'product_variant__sku',
        'product_variant__product__track__name',
        'product_variant__product__album__name',
        'product_variant__product__merch__name',
    )

    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        """Оптимизация запросов."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'user',
                'product_variant__product',
                'product_variant__product__track',
                'product_variant__product__album',
                'product_variant__product__merch',
            )
        )

    @admin.display(description='Пользователь', ordering='user__username')
    def get_user_info(self, obj):
        """Отображение пользователя."""
        return obj.user

    @admin.display(description='Товар', ordering='product_variant__sku')
    def get_product_info(self, obj):
        """Отображение информации о товаре."""
        return obj.product_variant

    # Отображение формы редактирования
    fieldsets = (
        ('Основное', {'fields': ('user', 'product_variant')}),
        (
            'Системная информация',
            {'fields': ('created_at', 'updated_at')},
        ),
    )
    autocomplete_fields = ('user', 'product_variant')
    ordering = ('-created_at',)
