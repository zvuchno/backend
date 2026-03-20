"""Модуль админки для модели Album.

Содержит настройку интерфейса Django Admin для модели альбомов.
"""

from django.contrib import admin
from django.utils.html import format_html

from .mixins import AutoOwnerAdminMixin
from store.models import Album, Product, Track


class ProductInline(admin.StackedInline):
    """Инлайн для редактирования полей продукта, связанных с альбомом."""

    model = Product
    fields = ('base_price', 'allow_fans_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки'
    verbose_name_plural = 'Торговые настройки'


class TrackInline(admin.TabularInline):
    """Инлайн для списка треков (модель Track)."""

    model = Track
    fields = ('track_number', 'name', 'audio_file', 'is_active')
    extra = 1
    show_change_link = True
    ordering = ('track_number',)


@admin.register(Album)
class AlbumAdmin(AutoOwnerAdminMixin, admin.ModelAdmin):
    """Админка для модели Album с Inline треков и настроек продукта."""

    list_display = (
        'name',
        'genre',
        'is_single',
        'release_date',
        'is_active',
        'get_price',
        'get_allow_fans_overpay',
        'visibility',
    )

    search_fields = ('genre__name', 'name')

    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
        'visibility',
    )

    ordering = ('-created_at', 'is_active', 'name')
    readonly_fields = ('image_preview', 'created_at', 'updated_at', 'owner')
    list_editable = ('is_active', 'visibility')
    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'name',
                    'genre',
                    'is_single',
                    'release_date',
                    'description',
                    'cover_image',
                    'image_preview',
                    'is_active',
                    'visibility',
                    'owner',
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )
    inlines = (ProductInline, TrackInline)

    # Геттеры для отображения данных из связанного Product
    @admin.display(description='Цена')
    def get_price(self, obj):
        return (
            obj.product.base_price
            if hasattr(obj, 'product') and obj.product
            else '-'
        )

    @admin.display(description='Переплата')
    def get_allow_fans_overpay(self, obj):
        if hasattr(obj, 'product') and obj.product:
            return 'Да' if obj.product.allow_fans_overpay else 'Нет'
        return '-'

    @admin.display(description='Изображение')
    def image_preview(self, obj):
        """Возвращает HTML-превью обложки альбома в списке админки."""
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:4px;">',
                obj.cover_image.url,
            )
        return '-'
