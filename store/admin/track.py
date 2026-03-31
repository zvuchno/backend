"""Модуль админки для модели Track.

Содержит настройку интерфейса Django Admin для модели музыкального трека.
"""

from django.contrib import admin

from .mixins import AutoOwnerAdminMixin, CommerceMixin
from store.models import Product, Track


class ProductInline(admin.StackedInline):
    """Инлайн для редактирования полей продукта, связанных с треком."""

    model = Product
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки трека'


@admin.register(Track)
class TrackAdmin(AutoOwnerAdminMixin, CommerceMixin, admin.ModelAdmin):
    """Админка для модели Track."""

    list_display = (
        'name',
        'album',
        'position',
        'get_price',
        'get_allow_overpay',
        'is_active',
    )

    search_fields = ('album__name', 'lyrics', 'name')
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
    )
    ordering = ('album', 'position')
    readonly_fields = (
        'formatted_duration',
        'created_at',
        'updated_at',
        'owner',
    )
    list_editable = ('is_active',)
    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'name',
                    'album',
                    'is_active',
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

    @admin.display(description='Цена')
    def get_price(self, obj):
        """Геттер для отображения поля price из связанного Product."""
        if hasattr(obj, 'product') and obj.product:
            return obj.product.price
        return '-'

    @admin.display(description='Переплата', boolean=True)
    def get_allow_overpay(self, obj):
        """Геттер для отображения поля allow_overpay из связанного Product."""
        if hasattr(obj, 'product') and obj.product:
            return obj.product.allow_overpay
        return None

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return '-'
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f'{minutes}:{seconds:02}'
