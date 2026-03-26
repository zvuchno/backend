"""Модуль админки для модели Merch.

Содержит настройку интерфейса Django Admin для модели мерча.
"""


from django.contrib import admin
from django.utils.html import format_html
from nested_admin import (
    NestedModelAdmin,
    NestedTabularInline,
)

from store.admin.inlines import ProductInline
from store.admin.mixins import AutoOwnerAdminMixin
from store.models import AlbumMerch, Image, Merch


class PhotoInline(NestedTabularInline):
    """Отображение фото в модели мерча."""

    model = Image
    extra = 1
    fields = ('image', 'preview', 'is_main')
    readonly_fields = ('preview',)

    @admin.display(description='Превью')
    def preview(self, image):
        if image.image:
            return format_html(
                '<img src="{}" style="height:60px; border-radius:4px"/>',
                image.image.url,
            )
        return '-'


class AlbumMerchInline(NestedTabularInline):
    """Отображение обложки альбома в админке мерча."""

    model = AlbumMerch
    extra = 1
    fields = ('album', 'preview')
    readonly_fields = ('preview',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('album')

    @admin.display(description='Фото альбома')
    def preview(self, album):
        if album.album:
            return format_html(
                '<img src="{}" style="height:75px; border-radius:4px"/>',
                album.album.cover_image.url,
            )
        return '-'


@admin.register(Merch)
class MerchAdmin(AutoOwnerAdminMixin, NestedModelAdmin):
    """Админка мерча."""

    inlines = (PhotoInline, AlbumMerchInline, ProductInline)
    list_display = (
        'name',
        'kind',
        'owner',
        'created_at',
        'image_preview',
        'is_published',
        'get_price',
        'get_allow_overpay',
        'visibility',
        'is_active',
    )
    list_editable = (
        'is_active', 'is_published', 'visibility',
    )
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
        'visibility',
        'kind',
    )
    search_fields = (
        'name',
        'kind__name',
        'owner__username',
    )
    ordering = ('-created_at',)
    search_help_text = 'Поиск по названию, категории, типу и владельцу'
    readonly_fields = ('image_preview', 'created_at', 'updated_at', 'owner')

    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'kind',
                    'name',
                    'description',
                    'image_preview',
                    'is_published',
                    'is_carrier',
                    'visibility',
                    'owner',
                    'created_at',
                    'updated_at',
                    'is_active',
                ),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'product', 'kind'
        ).prefetch_related('images_merch')

    @admin.display(description='Цена')
    def get_price(self, obj):
        if hasattr(obj, 'product') and obj.product:
            return obj.product.price
        return '-'

    @admin.display(description='Переплата')
    def get_allow_overpay(self, obj):
        if hasattr(obj, 'product') and obj.product:
            return 'Да' if obj.product.allow_overpay else 'Нет'
        return '-'

    @admin.display(description='Главное фото')
    def image_preview(self, obj):
        image_obj = obj.images_merch.filter(is_main=True).first()
        if image_obj:
            return format_html(
                '<img src="{}" width="150" height="100" />',
                image_obj.image.url,
            )
        return '-'
