"""Модуль админки профиля артиста."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from users.admin.mixins import ImagePreviewMixin
from users.models import (
    ArtistContact,
    ArtistPickupPoint,
    ArtistProfile,
    ArtistShippingPoint,
    ArtistSocial,
)


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


class ArtistPickupPointInline(admin.TabularInline):
    """Связанные адреса самовывоза."""

    model = ArtistPickupPoint
    can_delete = True
    fk_name = 'artist'
    extra = 0


class ArtistShippingPointInline(admin.TabularInline):
    """Связанный ShippingPoint."""

    model = ArtistShippingPoint
    can_delete = True
    fk_name = 'artist'
    extra = 0


@admin.register(ArtistProfile)
class ArtistProfileAdmin(ImagePreviewMixin, admin.ModelAdmin):
    """Админка профиля артиста."""

    inlines = (
        ArtistContactInline,
        ArtistPickupPointInline,
        ArtistShippingPointInline,
        ArtistSocialInline,
    )
    list_display = (
        'id',
        'profile_type',
        'user',
        'label',
        'name',
        'city',
        'is_active',
        'created_at',
    )
    list_display_links = ('id', 'name', 'user')
    list_filter = (
        'profile_type',
        'is_active',
        'created_at',
    )
    readonly_fields = (
        'account_phone',
        'account_username',
        'user_link',
        'image_preview',
        'created_at',
        'updated_at',
        'display_connect_to_telegram',
    )
    search_fields = (
        'name',
        'city',
        'user__phone',
        'user__username',
        'user__email',
        'label__name',
    )
    ordering = ('-created_at',)
    autocomplete_fields = ('user', 'label')

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление объектов через админку."""
        return False

    def get_actions(self, request):
        """Убирает массовое удаление из списка действий."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    @admin.display(description='Учётная запись')
    def user_link(self, obj):
        if not obj or not obj.user_id:
            return '—'

        url = reverse(
            'admin:users_coreuser_change',
            args=(obj.user_id,),
        )
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.user.email,
        )

    @admin.display(description='Телефон учетной записи')
    def account_phone(self, obj):
        if not obj or not obj.user_id:
            return '—'
        return obj.user.phone or '—'

    @admin.display(description='Имя пользователя')
    def account_username(self, obj):
        if not obj or not obj.user_id:
            return '—'

        return obj.user.username or '—'

    @admin.display(description='Подключен Telegram-bot', boolean=True)
    def display_connect_to_telegram(self, obj):
        """Отображает статус подключения к Telegram-боту."""
        return bool(obj.telegram_chat_id)

    def get_fieldsets(self, request, obj=None):
        """Возвращает набор полей для создания и редактирования артиста."""
        fieldsets = [
            (
                'Основная информация',
                {
                    'fields': (
                        'name',
                        'description',
                        'city',
                    ),
                },
            ),
            (
                'Обложка',
                {
                    'fields': (
                        'cover',
                        'image_preview',
                    ),
                },
            ),
            (
                'Статус',
                {
                    'fields': ('is_active',),
                },
            ),
        ]

        if obj is None:
            fieldsets.insert(
                0,
                (
                    'Тип и управление',
                    {
                        'fields': (
                            'profile_type',
                            'user',
                            'label',
                        ),
                    },
                ),
            )
            fieldsets.append(
                (
                    'Ссылки',
                    {
                        'fields': ('url',),
                    },
                ),
            )
        else:
            fieldsets.insert(
                0,
                (
                    'Тип и управление',
                    {
                        'fields': (
                            'profile_type',
                            'label',
                            'user_link',
                            'account_username',
                            'account_phone',
                            'display_connect_to_telegram',
                        ),
                    },
                ),
            )
            fieldsets.append(
                (
                    'Ссылки',
                    {
                        'fields': ('url',),
                    },
                ),
            )
            fieldsets.append(
                (
                    'Системная информация',
                    {
                        'fields': (
                            'created_at',
                            'updated_at',
                        ),
                    },
                ),
            )

        return fieldsets
