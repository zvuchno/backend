"""Модуль админки учетной записи.

Содержит класс админки пользователя,
inlines для слушателя и артиста.
Добавлены флаги наличия профиля артиста и слушателя.
"""

from urllib.parse import urlencode

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Exists, OuterRef
from django.urls import reverse
from django.utils.html import format_html

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

    def get_queryset(self, request):
        """Загружает пользователя вместе с профилем."""
        return super().get_queryset(request).select_related('user')


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
        'slug',
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
        return obj.has_listener_profile

    @admin.display(description='Артист', boolean=True)
    def is_artist(self, obj):
        """Есть ли профиль артиста."""
        return obj.has_artist_profile

    @admin.display(description='Юридический профиль')
    def legal_profile_link(self, obj):
        if not obj or not obj.pk:
            return '—'

        legal_profile = getattr(obj, 'legal_profile', None)

        if legal_profile:
            url = reverse(
                'admin:users_artistlegalprofile_change',
                args=(legal_profile.pk,),
            )
            return format_html(
                '<a href="{}">Открыть юридический профиль</a>',
                url,
            )

        url = reverse('admin:users_artistlegalprofile_add')
        url = f'{url}?{urlencode({"user": obj.pk})}'

        return format_html(
            '<a href="{}">Не создан. Создать?</a>',
            url,
        )

    @admin.display(description='Юридический профиль')
    def legal_profile_link(self, obj):
        if not obj or not obj.pk:
            return '—'

        legal_profile = getattr(obj, 'legal_profile', None)

        if legal_profile:
            url = reverse(
                'admin:users_artistlegalprofile_change',
                args=(legal_profile.pk,),
            )
            return format_html(
                '<a href="{}">Открыть юридический профиль</a>',
                url,
            )

        url = reverse('admin:users_artistlegalprofile_add')
        url = f'{url}?{urlencode({"user": obj.pk})}'

        return format_html(
            '<a href="{}">Не создан. Создать?</a>',
            url,
        )

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
        'phone',
        'artist_profile__name',
        'artist_profile__slug',
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
                'fields': (
                    'is_email_verified',
                    'is_phone_verified',
                ),
            },
        ),
        (
            'Юридические данные',
            {
                'fields': ('legal_profile_link',),
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
    readonly_fields = (
        'last_login',
        'date_joined',
        'legal_profile_link',
    )
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

    def get_queryset(self, request):
        """Оптимизирует проверку наличия профилей."""
        return (
            super()
            .get_queryset(request)
            .annotate(
                has_listener_profile=Exists(
                    ListenerProfile.objects.filter(
                        user=OuterRef('pk'),
                    ),
                ),
                has_artist_profile=Exists(
                    ArtistProfile.objects.filter(
                        user=OuterRef('pk'),
                    ),
                ),
            )
        )
