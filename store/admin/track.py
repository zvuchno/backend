"""Модуль админки для модели Track.

Содержит настройку интерфейса Django Admin для модели музыкального трека.
"""

from django.contrib import admin

from .mixins import AutoOwnerAdminMixin
from store.models import Product, Track


class ProductInline(admin.StackedInline):
    """Инлайн для редактирования полей продукта, связанных с треком."""

    model = Product
    fields = ('base_price', 'allow_fans_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки трека'


@admin.register(Track)
class TrackAdmin(AutoOwnerAdminMixin, admin.ModelAdmin):
    """Админка для модели Track."""

    list_display = (
        'name',
        'album',
        'track_number',
        'is_active',
        'get_price',
        'get_allow_fans_overpay',
    )

    search_fields = ('album__name', 'lyrics', 'name')
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
    )
    ordering = ('album', 'track_number')
    readonly_fields = (
        'formatted_duration',
        'created_at',
        'updated_at',
        'owner',
    )
    list_editable = (
        'is_active',
        'track_number',
    )
    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'name',
                    'album',
                    'is_active',
                    'track_number',
                    'audio_file',
                    'formatted_duration',
                    'lyrics',
                    'owner',
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )
    inlines = (ProductInline,)

    # Геттеры для данных из связанного Product
    @admin.display(description='Цена (индив.)')
    def get_price(self, obj):
        if hasattr(obj, 'product') and obj.product:
            return obj.product.base_price
        return '-'

    @admin.display(description='Переплата')
    def get_allow_fans_overpay(self, obj):
        if hasattr(obj, 'product') and obj.product:
            return 'Да' if obj.product.allow_fans_overpay else 'Нет'
        return '-'

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return '-'
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f'{minutes}:{seconds:02}'
