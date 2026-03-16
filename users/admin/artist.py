"""
Модуль админки профиля артиста.

Добавлены inlines контактов и соцсетей, превью обложки.
"""

from django.contrib import admin

from users.admin.mixins import ImagePreviewMixin
from users.models import ArtistContact, ArtistSocial, ArtistProfile


class ArtistContactInline(admin.TabularInline):
    """Связанные контакты."""
    model = ArtistContact
    can_delete = True
    fk_name = 'artist'
    extra = 0


class ArtistSocialInline(admin.TabularInline):
    """Связанные ссылки на соцсети."""
    model = ArtistSocial
    can_delete = True
    fk_name = 'artist'
    extra = 0


@admin.register(ArtistContact)
class ArtistContactAdmin(admin.ModelAdmin):
    """Для контактов артиста."""

    list_display = (
        'id',
        'artist',
        'label',
        'value',
    )
    list_display_links = ('id', 'label',)
    search_fields = (
        'artist__user__email',
        'artist__user__username',
        'value',
    )


@admin.register(ArtistSocial)
class ArtistSocialAdmin(admin.ModelAdmin):
    """Для ссылок на соцсети артиста."""

    list_display = (
        'id',
        'artist',
        'label',
        'value',
    )
    list_display_links = ('id', 'label',)
    search_fields = (
        'artist__user__email',
        'artist__user__username',
        'value',
    )


@admin.register(ArtistProfile)
class ArtistProfileAdmin(ImagePreviewMixin, admin.ModelAdmin):
    """Админка профиля артиста."""

    inlines = (ArtistContactInline, ArtistSocialInline)
    list_display = (
        'id',
        'owner',
        'name',
        'city',
        'url',
        'is_active',
        'created_at',
    )
    list_display_links = ('id', 'name')
    list_filter = (
        'is_active',
        'created_at',
    )
    readonly_fields = (
        'image_preview',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'name',
        'phone',
        'city',
        'owner__username',
        'owner__email',
    )
    ordering = ('-created_at',)
    autocomplete_fields = ('owner',)

    def get_fieldsets(self, request, obj=None):
        """В интерфейсе добавления артиста скрывает created_at, updated_at."""
        fieldsets = [
            ('Пользователь', {
                'fields': ('owner',)
            }),
            ('Основная информация', {
                'fields': (
                    'name',
                    'description',
                    'city',
                )
            }),
            ('Обложка', {
                'fields': (
                    'cover',
                    'image_preview',
                )
            }),
            ('Контакты и ссылки', {
                'fields': (
                    'phone',
                    'url',
                )
            }),
            ('Статус', {
                'fields': ('is_active',)
            }),
        ]

        if obj:
            fieldsets.append(
                ('Системная информация', {
                    'fields': (
                        'created_at',
                        'updated_at',
                    )
                })
            )
        return fieldsets
