"""Модель профиля артиста."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models
from slugify import slugify

from common.models.abstract import ActivatableModel, TimestampModel
from common.storages import get_public_media_storage

from store.validators import validate_file_size
from users.constants import (
    ARTIST_DESC_FIELD_MAX_LENGTH,
    ARTIST_DESC_FIELD_MIN_LENGTH,
    ARTIST_LINK_TYPE_MAX_LENGTH,
    ARTIST_NAME_FIELD_MAX_LENGTH,
    ARTIST_NAME_FIELD_MIN_LENGTH,
    CITY_FIELD_MAX_LENGTH,
    CITY_FIELD_MIN_LENGTH,
)
from users.upload_paths import artist_cover_upload_to


class ArtistProfileType(models.TextChoices):
    """Тип публичного профиля."""

    ARTIST = 'artist', 'Артист'
    LABEL = 'label', 'Лейбл'


class ArtistProfile(ActivatableModel, TimestampModel):
    """Публичный профиль артиста или лейбла.

    Профиль артиста может существовать без собственной учётной записи,
    если он создан и управляется лейблом. Профиль лейбла всегда связан
    с учётной записью.
    TODO: название модели уже не отражает смысл.
    """

    profile_type = models.CharField(
        'Тип профиля',
        max_length=ARTIST_LINK_TYPE_MAX_LENGTH,
        choices=ArtistProfileType.choices,
        default=ArtistProfileType.ARTIST,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='artist_profile',
        verbose_name='Учётная запись',
        null=True,
        blank=True,
    )
    label = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='artists',
        verbose_name='Лейбл',
        limit_choices_to={
            'profile_type': ArtistProfileType.LABEL,
        },
        null=True,
        blank=True,
    )
    name = models.CharField(
        'Имя артиста',
        max_length=ARTIST_NAME_FIELD_MAX_LENGTH,
        validators=[MinLengthValidator(ARTIST_NAME_FIELD_MIN_LENGTH)],
    )
    slug = models.SlugField(
        'slug',
        unique=True,
        blank=True,
        max_length=ARTIST_NAME_FIELD_MAX_LENGTH,
    )
    city = models.CharField(
        'Город',
        max_length=CITY_FIELD_MAX_LENGTH,
        blank=True,
        validators=[MinLengthValidator(CITY_FIELD_MIN_LENGTH)],
    )
    description = models.TextField(
        'Об исполнителе',
        blank=True,
        validators=[
            MinLengthValidator(ARTIST_DESC_FIELD_MIN_LENGTH),
            MaxLengthValidator(ARTIST_DESC_FIELD_MAX_LENGTH),
        ],
    )
    cover = models.ImageField(
        'Обложка артиста',
        upload_to=artist_cover_upload_to,
        storage=get_public_media_storage,
        blank=True,
        null=True,
        validators=(validate_file_size,),
    )
    telegram_chat_id = models.BigIntegerField(
        unique=True,
        blank=True,
        null=True,
    )
    telegram_token = models.UUIDField(
        unique=True,
        blank=True,
        null=True,
    )

    @property
    def default_payout_recipient(self):
        """Возвращает аккаунт получателя выплат по умолчанию."""
        payout_recipient = (
            self.label.user if self.label_id is not None else self.user
        )

        if payout_recipient is None:
            raise ValueError(
                'Для публичного профиля не настроен получатель выплат.',
            )

        return payout_recipient

    def _get_effective_store_setting(self, field_name: str) -> str:
        """Возвращает настройку магазина с учётом fallback на лейбл."""
        own_settings = getattr(self, 'store_settings', None)
        own_value = getattr(own_settings, field_name, None)

        if own_value:
            return own_value

        if self.label_id is None:
            return ''

        label_settings = getattr(self.label, 'store_settings', None)
        return getattr(label_settings, field_name, '') or ''

    @property
    def effective_support_email(self) -> str:
        """Возвращает существующий email поддержки."""
        return self._get_effective_store_setting('support_email')

    @property
    def effective_returns_email(self) -> str:
        """Возвращает существующий email для возвратов."""
        return self._get_effective_store_setting('returns_email')

    @property
    def effective_shipping_point(self):
        """Возвращает ПВЗ отправки с учётом fallback на лейбл."""
        shipping_point = getattr(self, 'shipping_point', None)

        if shipping_point is not None:
            return shipping_point

        if self.label_id is not None:
            return getattr(self.label, 'shipping_point', None)

        return None

    def get_effective_pickup_points(self):
        """Возвращает queryset точек самовывоза с учётом fallback на лейбл."""
        pickup_points = self.pickup_points.filter(is_active=True)

        if pickup_points.exists() or self.label_id is None:
            return pickup_points

        return self.label.pickup_points.filter(is_active=True)

    def save(self, *args, **kwargs):
        """Сохраняет профиль артиста и при необходимости создает slug.

        Если slug не был задан вручную, он формируется автоматически
        на основе имени артиста. При совпадении slug с уже существующим
        значением подбирается уникальный вариант с числовым суффиксом.
        """
        if not self.slug:
            slug = slugify(self.name)
            new_slug = slug
            slug_counter = 1
            while (
                ArtistProfile.objects
                .filter(slug=new_slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                new_slug = f'{slug}-{slug_counter}'
                slug_counter += 1
            self.slug = new_slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'артист'
        verbose_name_plural = 'артисты'
        ordering = ('name',)
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False)
                    | models.Q(label__isnull=False)
                ),
                name='artist_profile_has_user_or_label',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(profile_type=ArtistProfileType.ARTIST)
                    | models.Q(user__isnull=False)
                ),
                name='label_profile_has_user',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(profile_type=ArtistProfileType.ARTIST)
                    | models.Q(label__isnull=True)
                ),
                name='label_profile_has_no_parent_label',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(label__isnull=True)
                    | ~models.Q(pk=models.F('label'))
                ),
                name='profile_is_not_its_own_label',
            ),
        )

    def clean(self):
        """Проверяет корректность связи артиста с лейблом."""
        super().clean()

        if self.profile_type == ArtistProfileType.LABEL:
            if self.user_id is None:
                raise ValidationError({
                    'profile_type': (
                        'Профиль лейбла должен быть связан с учётной записью.'
                    ),
                })

            if self.label_id is not None:
                raise ValidationError({
                    'label': 'Профиль лейбла не может состоять в лейбле.',
                })

            return

        if self.user_id is None and self.label_id is None:
            raise ValidationError({
                'label': (
                    'Артист без собственной учётной записи '
                    'должен быть связан с лейблом.'
                ),
            })

        if self.label_id is None:
            return

        if self.pk is not None and self.label_id == self.pk:
            raise ValidationError({
                'label': 'Профиль не может быть собственным лейблом.',
            })

        if self.profile_type != ArtistProfileType.ARTIST:
            raise ValidationError({
                'label': 'Только профиль артиста может быть связан с лейблом.',
            })

        if self.label.profile_type != ArtistProfileType.LABEL:
            raise ValidationError({
                'label': 'Выбранный профиль не является лейблом.',
            })

    def __str__(self):
        return self.name
