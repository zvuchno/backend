from django.contrib import admin
from django.utils.html import format_html

from store.models import (
    Album, Genre, Track, Category, Kind, Merch, Image, AlbumMerch
)

from store.constants import MAX_IMAGE_FOR_MERCH


class AutoUserAdminMixin:

    def save_model(self, request, obj, form, change):
        # Если объект ещё не имеет user, ставим текущего
        if not getattr(obj, 'user_id', None):
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Album)
class AlbumAdmin(AutoUserAdminMixin, admin.ModelAdmin):

    list_display = (
        'name',
        'release_date',
        'genre',
        'price',
        'allow_fans_to_pay_more',
        'visibility',
    )
    search_fields = ('genre', 'name',)
    list_filter = ('genre', 'visibility',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'user',)
    list_editable = (
        'price',
        'allow_fans_to_pay_more',
        'visibility',
    )
    fieldsets = (
        ('Основные данные', {
            'fields': (
                'name',
                'genre',
                'release_date',
                'description',
                'cover_image',
                'visibility',
                'user',
                'created_at',
            )
        }),
        ('Цены и оплата', {
            'fields': ('price', 'allow_fans_to_pay_more',)
        }),
    )


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = (
        'name',
    )
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Track)
class TrackAdmin(AutoUserAdminMixin, admin.ModelAdmin):
    list_display = (
        'name',
        'album',
        'individual_price',
        'allow_fans_to_pay_more',
    )
    search_fields = ('album', 'lyrics', 'name',)
    list_filter = ('album', 'allow_fans_to_pay_more',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'user',)
    list_editable = (
        'individual_price',
        'allow_fans_to_pay_more',
    )
    fieldsets = (
        ('Основные данные', {
            'fields': (
                'name',
                'album',
                'audio_file',
                'lyrics',
                'user',
                'created_at',
            )
        }),
        ('Цены и оплата', {
            'fields': ('individual_price', 'allow_fans_to_pay_more',)
        }),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Админка категорий."""
    list_display = (
        'name',
        'slug'
    )
    list_filter = ('created_at', 'is_active')
    search_fields = ('name',)
    search_help_text = 'Поиск по имени'


@admin.register(Kind)
class KindAdmin(admin.ModelAdmin):
    """Админка типов мерча."""
    list_display = (
        'name',
        'slug'
    )
    list_filter = (
        'created_at',
        'is_active',
    )
    search_fields = (
        'name',
    )
    search_help_text = 'Поиск по имени'


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
                image.image.url
            )
        return '-'


class AlbumMerchInline(admin.TabularInline):
    """Отображение обложки альбома в админке мерча"""
    model = AlbumMerch
    fields = ('album', 'preview')
    readonly_fields = ('preview',)

    @admin.display(description='Фото альбома')
    def preview(self, album):
        if album.album:
            return format_html(
                '<img src="{}" style="height:100px; border-radius:4px"/>',
                album.album.cover_image.url
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
        'category',
        'kind',
        'owner',
        'created_at',
        'image_preview'
    )
    list_editable = (
        'price',
        'quantity',
        'kind',
        'category',
    )
    list_filter = (
        'created_at',
        'is_active',
        'kind',
        'category'
    )
    search_fields = (
        'name',
        'category__name',
        'kind__name',
        'owner__username'
    )
    search_help_text = 'Поиск по названию, категории, типу и владельцу'
    readonly_fields = ('image_preview', 'created_at')

    fieldsets = [
        ('Основная информация', {
            'fields': ('name', 'quantity', 'category', 'kind',
                       'owner', 'description', 'visibility',
                       'characteristic'),

        }),
        ('Финансы', {
            'fields': ('price', 'access_price_more'),
        })
    ]

    @admin.display(description='Главная картинка')
    def image_preview(self, image):
        for image_obj in image.images_merch.all()[:MAX_IMAGE_FOR_MERCH]:
            if image_obj.image:
                return format_html(
                    '<img src="{}" width="200" height="150" />',
                    image_obj.image.url
                )
        return '-'
