"""Модуль админки для модели Album.

Содержит настройку интерфейса Django Admin для модели альбомов.
"""

from django.contrib import admin
from django.utils.html import format_html

from .mixins import AutoOwnerAdminMixin
from store.models import Album, Track


class TrackInline(admin.TabularInline):
    """Inline для треков внутри формы альбома."""

    model = Track
    extra = 1
    min_num = 1
    readonly_fields = ('duration',)
    fields = (
        'track_number',
        'name',
        'album',
        'audio_file',
        'is_active',
        'individual_price',
        'allow_fans_overpay',
    )


@admin.register(Album)
class AlbumAdmin(AutoOwnerAdminMixin, admin.ModelAdmin):
    """Админка для модели Album с Inline треков."""

    list_display = (
        'name',
        'genre',
        'release_date',
        'is_active',
        'price',
        'allow_fans_overpay',
        'visibility',
    )
    search_fields = ('genre', 'name')
    list_filter = (
        'visibility',
        'is_active',
        'created_at',
        'updated_at',
    )
    ordering = ('name', 'is_active')
    readonly_fields = ('image_preview', 'created_at', 'updated_at', 'owner')
    list_editable = (
        'price',
        'allow_fans_overpay',
        'is_active',
        'visibility',
    )
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
        (
            'Цены и оплата',
            {
                'fields': ('price', 'allow_fans_overpay'),
            },
        ),
    )
    inlines = (TrackInline,)

    @admin.display(description='Изображение')
    def image_preview(self, obj):
        """Возвращает HTML-превью обложки альбома в списке админки."""
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:4px;">',
                obj.cover_image.url,
            )
        return ''
