"""Модуль админки для модели Track.

Содержит настройку интерфейса Django Admin для модели музыкального трека.
"""

from django.contrib import admin

from .mixins import (
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.models import Product, Track


class ProductInline(admin.StackedInline):
    """Инлайн для редактирования полей продукта, связанных с треком."""

    model = Product
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки трека'


@admin.register(Track)
class TrackAdmin(
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
    admin.ModelAdmin,
):
    """Админка для модели Track."""

    list_display = (
        'name',
        'album',
        'owner',
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
        'get_sku',
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
                    'get_sku',
                    'owner',
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )
    inlines = (ProductInline,)

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return '-'
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f'{minutes}:{seconds:02}'

    def get_queryset(self, request):
        """Родительский метод миксина + select_related('album', 'owner')."""
        return super().get_queryset(request).select_related('album', 'owner')
