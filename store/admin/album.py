"""Модуль админки для модели Album.

Содержит настройку интерфейса Django Admin для модели альбомов.
"""

from django.contrib import admin
from django.utils.html import format_html
from nested_admin import (
    NestedModelAdmin,
    NestedStackedInline,
    NestedTabularInline,
)

from .mixins import AutoOwnerAdminMixin
from store.models import Album, Product, ProductVariant, Track


class TrackInline(NestedTabularInline):
    """Инлайн для списка треков (модель Track)."""

    model = Track
    fields = ('position', 'name', 'audio_file', 'duration', 'is_active')
    readonly_fields = ('duration',)
    extra = 0  # Чтобы Nested-сортировка не требовала заполнять пустое поле
    show_change_link = True
    ordering = ('position',)
    sortable_field_name = 'position'


class ProductVariantInline(NestedTabularInline):
    """Инлайн для редактирования вариантов продукта в админке."""

    model = ProductVariant
    fields = ('carrier', 'price', 'sku', 'stock')
    extra = 1

    def get_queryset(self, request):
        """Подтянуть связанные с ProductVariant поля."""
        qs = super().get_queryset(request)
        return qs.select_related('carrier')


class ProductInline(NestedStackedInline):
    """Инлайн продукта с вложенными вариантами."""

    model = Product
    inlines = (ProductVariantInline,)
    fields = ('allow_overpay',)
    can_delete = False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Album)
class AlbumAdmin(AutoOwnerAdminMixin, NestedModelAdmin):
    """Админка модели Album с поддержкой вложенных inline.

    Отображает:
    - Основные поля альбома.
    - Инлайн Product и его варианты (ProductInline).
    - Инлайн Track (TrackInline).

    Особенности:
    - Переход на NestedModelAdmin позволяет редактировать вложенные объекты
      прямо в форме альбома.
    """

    list_select_related = ('product', 'genre')  # Подтянуть одним запросом в БД
    list_display = (
        'name',
        'genre',
        'is_single',
        'release_date',
        'is_active',
        'get_allow_overpay',
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

    @admin.display(description='Переплата')
    def get_allow_overpay(self, obj):
        """Геттер для отображения поля allow_overpay из связанного Product."""
        if hasattr(obj, 'product') and obj.product:
            return 'Да' if obj.product.allow_overpay else 'Нет'
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
