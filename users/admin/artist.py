"""Модуль админки профиля артиста."""

from urllib.parse import urlencode

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from common.services import get_artist_publication_readiness

from users.admin.mixins import ImagePreviewMixin
from users.models import (
    ArtistContact,
    ArtistPickupPoint,
    ArtistProfile,
    ArtistProfileType,
    ArtistShippingPoint,
    ArtistSocial,
    ArtistStoreSettings,
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


class ArtistStoreSettingsInline(admin.TabularInline):
    """Настройки возвратов."""

    model = ArtistStoreSettings
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
        ArtistStoreSettingsInline,
    )
    list_display = (
        'id',
        'name',
        'slug',
        'profile_type',
        'label',
        'user',
        'city',
        'is_active',
        'sales_readiness',
        'created_at',
    )
    list_display_links = ('id', 'name')
    list_filter = (
        'profile_type',
        'is_active',
        'created_at',
    )
    readonly_fields = (
        'account_phone',
        'account_username',
        'user_link',
        'sales_ready',
        'digital_sales_ready',
        'physical_sales_ready',
        'payout_legal_profile_verified',
        'shipping_point_ready',
        'payout_legal_profile_link',
        'managed_artists',
        'image_preview',
        'created_at',
        'updated_at',
        'display_connect_to_telegram',
    )
    search_fields = (
        'name',
        'slug',
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

    @admin.display(description='Управляемые артисты')
    def managed_artists(self, obj):
        """Отображает артистов, которыми управляет лейбл."""
        if not obj or not obj.pk or not obj.artists.exists():
            return '—'

        return format_html_join(
            ', ',
            '<a href="{}">{}</a>',
            (
                (
                    reverse(
                        'admin:users_artistprofile_change',
                        args=(artist.pk,),
                    ),
                    artist.name,
                )
                for artist in obj.artists.order_by('name')
            ),
        )

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

    @admin.display(description='Продажи')
    def sales_readiness(self, obj):
        readiness = get_artist_publication_readiness(obj)

        if readiness.can_publish_physical:
            return 'Все типы'

        if readiness.can_publish_digital:
            return 'Цифровые'

        return 'Не готов'

    @admin.display(description='Готов к продажам', boolean=True)
    def sales_ready(self, obj):
        readiness = get_artist_publication_readiness(obj)
        return readiness.can_publish_digital

    @admin.display(description='Цифровые продажи')
    def digital_sales_ready(self, obj):
        readiness = get_artist_publication_readiness(obj)

        if readiness.can_publish_digital:
            return 'Доступны'

        return ', '.join(
            requirement.description
            for requirement in readiness.digital_missing
        )

    @admin.display(description='Физические продажи')
    def physical_sales_ready(self, obj):
        readiness = get_artist_publication_readiness(obj)

        if readiness.can_publish_physical:
            return 'Доступны'

        return ', '.join(
            requirement.description
            for requirement in readiness.physical_missing
        )

    @admin.display(description='ПВЗ / СДЭК настроен', boolean=True)
    def shipping_point_ready(self, obj):
        return obj.effective_shipping_point is not None

    @admin.display(description='Юр. данные подтверждены', boolean=True)
    def payout_legal_profile_verified(self, obj):
        payout_recipient = obj.default_payout_recipient
        legal_profile = getattr(payout_recipient, 'legal_profile', None)

        return bool(legal_profile and legal_profile.is_verified)

    @admin.display(description='Юридический профиль получателя выплат')
    def payout_legal_profile_link(self, obj):
        if not obj or not obj.pk:
            return '—'

        # Для управляемого артиста получателем является лейбл.
        if obj.profile_type == ArtistProfileType.ARTIST and obj.label_id:
            label = obj.label
            label_url = reverse(
                'admin:users_artistprofile_change',
                args=(label.pk,),
            )

            if not label.user_id:
                return format_html(
                    'У лейбла нет учётной записи — '
                    '<a href="{}">перейти к профилю лейбла</a>',
                    label_url,
                )

            legal_profile = getattr(label.user, 'legal_profile', None)

            if not legal_profile:
                return format_html(
                    'Не создан — <a href="{}">перейти к профилю лейбла</a>',
                    label_url,
                )

            legal_profile_url = reverse(
                'admin:users_artistlegalprofile_change',
                args=(legal_profile.pk,),
            )
            return format_html(
                '<a href="{}">Юридический профиль лейбла «{}»</a>',
                legal_profile_url,
                label.name,
            )

        if not obj.user_id:
            return 'Учётная запись не настроена'

        legal_profile = getattr(obj.user, 'legal_profile', None)

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
        url = f'{url}?{urlencode({"user": obj.user_id})}'

        return format_html(
            '<a href="{}">Не создан. Создать?</a>',
            url,
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
                        'slug',
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
        else:
            management_fields = [
                'profile_type',
                'label',
                'user_link',
                'account_username',
                'account_phone',
                'display_connect_to_telegram',
            ]

            if obj.profile_type == ArtistProfileType.LABEL:
                management_fields.append('managed_artists')

            fieldsets.insert(
                0,
                (
                    'Тип и управление',
                    {
                        'fields': tuple(management_fields),
                    },
                ),
            )
            fieldsets.insert(
                1,
                (
                    'Доступ к продажам',
                    {
                        'fields': (
                            'sales_ready',
                            'digital_sales_ready',
                            'physical_sales_ready',
                            'payout_legal_profile_verified',
                            'shipping_point_ready',
                            'payout_legal_profile_link',
                        ),
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
