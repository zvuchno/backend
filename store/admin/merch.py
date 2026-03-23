"""Модуль админки для модели Merch.

Содержит настройку интерфейса Django Admin для модели мерча.
"""

from django.contrib import admin
from django.utils.html import format_html

from store.constants import MAX_IMAGE_FOR_MERCH
from store.models import AlbumMerch, Image, Merch


class PhotoInline(admin.TabularInline):
    """Отображение фото в модели мерча."""

    model = Image
    max_num = 4
    fields = ('image', 'preview')
    readonly_fields = ('preview',)

    @admin.display(description='Превью')
    def preview(self, image):
        if image.image:
            return format_html(
                '<img src="{}" style="height:100px; border-radius:4px"/>',
                image.image.url,
            )
        return '-'


class AlbumMerchInline(admin.TabularInline):
    """Отображение обложки альбома в админке мерча."""

    model = AlbumMerch
    fields = ('album', 'preview')
    readonly_fields = ('preview',)

    @admin.display(description='Фото альбома')
    def preview(self, album):
        if album.album:
            return format_html(
                '<img src="{}" style="height:100px; border-radius:4px"/>',
                album.album.cover_image.url,
            )
        return '-'


@admin.register(Merch)
class MerchAdmin(admin.ModelAdmin):
    """Админка мерча."""

    inlines = (PhotoInline, AlbumMerchInline)
    list_display = (
        'name',
        'price',
        'quantity',
        'kind',
        'owner',
        'created_at',
        'image_preview',
    )
    list_editable = (
        'price',
        'quantity',
        'kind',
    )
    list_filter = (
        'created_at',
        'is_active',
        'kind',
    )
    search_fields = (
        'name',
        'kind__name',
        'owner__username',
    )
    search_help_text = 'Поиск по названию, категории, типу и владельцу'
    readonly_fields = ('image_preview', 'created_at')

    fieldsets = [
        (
            'Основная информация',
            {
                'fields': (
                    'name',
                    'quantity',
                    'kind',
                    'owner',
                    'description',
                    'visibility',
                    'characteristic',
                ),
            },
        ),
        (
            'Финансы',
            {
                'fields': ('price', 'allow_fans_overpay'),
            },
        ),
    ]

    @admin.display(description='Главная картинка')
    def image_preview(self, image):
        for image_obj in image.images_merch.all()[:MAX_IMAGE_FOR_MERCH]:
            if image_obj.image:
                return format_html(
                    '<img src="{}" width="200" height="150" />',
                    image_obj.image.url,
                )
        return '-'
