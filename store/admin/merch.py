"""Модуль админки для модели Merch.

Содержит настройку интерфейса Django Admin для модели мерча.
"""

from django.contrib import admin
from django.utils.html import format_html
from nested_admin import (
    NestedModelAdmin,
    NestedStackedInline,
    NestedTabularInline,
)

from store.admin.mixins import (
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.models import Image, Merch, Product, ProductVariant


class ProductVariantInline(NestedTabularInline):
    """Инлайн для редактирования вариантов продукта в админке."""

    model = ProductVariant
    fields = ('sku', 'property_value', 'stock', 'is_active', 'updated_at')
    extra = 0
    readonly_fields = ('sku', 'updated_at')


class ProductInline(NestedStackedInline):
    """Инлайн продукта с вложенными вариантами."""

    model = Product
    inlines = (ProductVariantInline,)
    fields = ('price', 'allow_overpay', 'property_name')
    can_delete = False

    def has_delete_permission(self, request, obj=None):
        return False


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


@admin.register(Merch)
class MerchAdmin(
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
    NestedModelAdmin,
):
    """Админка мерча."""

    inlines = (PhotoInline, ProductInline)
    list_display = (
        'name',
        'kind',
        'owner',
        'image_preview',
        'album',
        'is_published',
        'get_price',
        'get_allow_overpay',
        'visibility',
        'is_active',
    )
    list_editable = (
        'is_active',
        'is_published',
        'visibility',
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
        'album__name',
    )
    ordering = ('-created_at',)
    search_help_text = 'Поиск по названию, типу, названию альбома и владельцу'
    readonly_fields = (
        'image_preview',
        'display_is_carrier',
        'created_at',
        'updated_at',
        'owner',
    )
    autocomplete_fields = ('album', 'kind')

    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'kind',
                    'name',
                    'description',
                    'image_preview',
                    'album',
                    'is_published',
                    'display_is_carrier',
                    'visibility',
                    'owner',
                    'is_active',
                ),
            },
        ),
        (
            'Системная информация',
            {
                'classes': ('collapse',),
                'fields': (
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )

    @admin.display(description='Носитель', boolean=True)
    def display_is_carrier(self, obj):
        """Отображает статус носителя для мерча."""
        return obj.is_carrier

    def get_queryset(self, request):
        qs = super(NestedModelAdmin, self).get_queryset(request)
        return qs.select_related(
            'product',
            'kind',
            'owner',
            'album',
        ).prefetch_related(
            'images_merch',
            'product__variants',
        )

    @admin.display(description='Главное фото')
    def image_preview(self, obj):
        images = list(obj.images_merch.all())

        for image in images:
            if image.is_main:
                return format_html(
                    '<img src="{}" style="max-height:100px; width:auto;" />',
                    image.image.url,
                )

        image = images[0] if images else None
        if image:
            return format_html(
                '<img src="{}" style="max-height:100px; width:auto;" />',
                image.image.url,
            )
        return '-'
