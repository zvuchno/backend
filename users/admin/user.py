"""Модуль админки учетной записи.

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
    """Инлайн для профиля слушателя."""

    model = ListenerProfile
    can_delete = False
    fk_name = 'user'
    extra = 1
    min_num = 1
    validate_min = True
    max_num = 1
    fields = ('full_name', 'is_active')


class ArtistProfileInline(ImagePreviewMixin, admin.StackedInline):
    """Инлайн для профиля артиста."""

    model = ArtistProfile
    can_delete = False
    fk_name = 'user'
    extra = 0
    readonly_fields = ('image_preview',)
    fields = (
        'name',
        'description',
        'cover',
        'image_preview',
        'city',
        'url',
        'is_active',
    )


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    """Админка для кастомной модели пользователя."""

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление объектов через админку."""
        return False

    def get_actions(self, request):
        """Убирает массовое удаление из списка действий."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    inlines = (ListenerProfileInline, ArtistProfileInline)

    @admin.display(description='Слушатель', boolean=True)
    def is_listener(self, obj):
        """Есть ли профиль слушателя."""
        return hasattr(obj, 'listener_profile')

    @admin.display(description='Артист', boolean=True)
    def is_artist(self, obj):
        """Есть ли профиль артиста."""
        return hasattr(obj, 'artist_profile')

    def save_related(self, request, form, formsets, change):
        """Сохраняет inlines и гарантирует наличие профиля слушателя."""
        super().save_related(request, form, formsets, change)
        ListenerProfile.objects.get_or_create(user=form.instance)

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
        (
            'Данные для аутентификации',
            {
                'fields': ('email', 'username', 'phone', 'password'),
            },
        ),
        (
            'Подтверждение контактов',
            {
                'fields': ('is_email_verified', 'is_phone_verified'),
            },
        ),
        (
            'Системная информация',
            {
                'fields': ('last_login', 'date_joined'),
            },
        ),
        (
            'Права доступа',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                ),
                'classes': ('collapse',),
            },
        ),
    )
    readonly_fields = ('last_login', 'date_joined')
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'username',
                    'phone',
                    'password1',
                    'password2',
                    'is_active',
                    'is_staff',
                ),
            },
        ),
    )
