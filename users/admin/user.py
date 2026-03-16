"""
Модуль админки учетной записи.

Содержит класс админки пользователя,
inlines для слушателя и артиста.
Добавлены флаги наличия профиля артиста и слушателя.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from users.admin.mixins import ImagePreviewMixin
from users.models import (
    ArtistProfile,
    ListenerProfile,
)

User = get_user_model()


class ListenerProfileInline(admin.StackedInline):
    model = ListenerProfile
    can_delete = False
    fk_name = 'user'
    extra = 0


class ArtistProfileInline(ImagePreviewMixin, admin.StackedInline):
    model = ArtistProfile
    can_delete = False
    fk_name = 'owner'
    extra = 0
    readonly_fields = ('image_preview',)
    fields = (
        'name',
        'description',
        'cover',
        'image_preview',
        'city',
        'phone',
        'url',
        'is_active',
    )


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    """Админка для кастомной модели пользователя."""
    inlines = (ListenerProfileInline, ArtistProfileInline)
    list_display = (
        'id',
        'email',
        'username',
        'is_listener',
        'is_artist',
        'is_staff',
        'is_superuser',
        'is_active',
        'date_joined',
        'last_login',
    )
    list_display_links = ('id', 'email', 'username')
    list_filter = (
        'is_staff',
        'is_superuser',
        'is_active',
        'date_joined',
    )
    search_fields = (
        'email',
        'username',
    )
    ordering = ('-date_joined',)
    fieldsets = (
        ('Данные для аутентификации', {
            'fields': ('email', 'username', 'password')
        }),
        ('Права доступа', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            )
        }),
        ('Важные даты', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'username',
                'password1',
                'password2',
                'is_active',
                'is_staff',
            ),
        }),
    )

    @admin.display(description='Слушатель', boolean=True)
    def is_listener(self, obj):
        """Есть ли профиль слушателя."""
        return hasattr(obj, 'listener_profile')

    @admin.display(description='Артист', boolean=True)
    def is_artist(self, obj):
        """Есть ли профиль артиста."""
        return hasattr(obj, 'artist_profile')
