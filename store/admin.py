"""
Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from django.contrib import admin
from django.utils.html import format_html

from store.constants import MAX_IMAGE_FOR_MERCH
from store.models import (
    Album,
    AlbumMerch,
    Category,
    Genre,
    Image,
    Kind,
    Merch,
    Track,
)


class AutoOwnerAdminMixin:
    """Mixin: автоматически назначает владельца при сохранении объектов."""

    def save_model(self, request, obj, form, change):
        """Назначает пользователя владельцем при сохранении через админку."""
        if not getattr(obj, 'user_id', None):
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        Назначает текущего пользователя владельцем
        для всех объектов из Inline при сохранении формы.
        """
        instances = formset.save(commit=False)
        for obj in instances:
            if not getattr(obj, 'owner_id', None):
                obj.owner = request.user
            obj.save()
        formset.save_m2m()


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
    search_fields = ('genre', 'name',)
    list_filter = (
        'visibility',
        'is_active',
        'created_at',
        'updated_at',
    )
    ordering = ('name', 'is_active',)
    readonly_fields = ('image_preview', 'created_at', 'updated_at', 'owner',)
    list_editable = (
        'price',
        'allow_fans_overpay',
        'is_active',
        'visibility',
    )
    fieldsets = (
        ('Основные данные', {
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
            )
        }),
        ('Цены и оплата', {
            'fields': ('price', 'allow_fans_overpay',)
        }),
    )
    inlines = (TrackInline,)

    @admin.display(description='Изображение')
    def image_preview(self, obj):
        """Возвращает HTML-превью обложки альбома в списке админки."""
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:4px;">',
                obj.cover_image.url
            )
        return ''


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    """Админка для модели Genre."""

    list_display = (
        'name',
        'slug',
        'is_active',
    )
    search_fields = ('name',)
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    ordering = ('name', 'is_active',)


@admin.register(Track)
class TrackAdmin(AutoOwnerAdminMixin, admin.ModelAdmin):
    """Админка для модели Track."""

    list_display = (
        'name',
        'album',
        'track_number',
        'is_active',
        'individual_price',
        'allow_fans_overpay',
    )
    search_fields = ('album', 'lyrics', 'name',)
    list_filter = (
        'is_active',
        'allow_fans_overpay',
        'created_at',
        'updated_at',
    )
    ordering = ('track_number', 'name',)
    readonly_fields = (
        'formatted_duration',
        'created_at',
        'updated_at',
        'owner',
    )
    list_editable = (
        'individual_price',
        'allow_fans_overpay',
        'is_active',
        'track_number',
    )
    fieldsets = (
        ('Основные данные', {
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
            )
        }),
        ('Цены и оплата', {
            'fields': ('individual_price', 'allow_fans_overpay',)
        }),
    )

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return "-"
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f"{minutes}:{seconds:02}"


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
    """Отображение обложки альбома в админке мерча."""

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
            'fields': ('price', 'allow_fans_overpay'),
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
