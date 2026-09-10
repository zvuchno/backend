from django.db import models

from common.models.abstract import TimestampModel


class ArtistStoreSettings(TimestampModel):
    """Настройки магазина артиста или лейбла."""

    artist = models.OneToOneField(
        'users.ArtistProfile',
        on_delete=models.CASCADE,
        related_name='store_settings',
        verbose_name='Профиль',
    )
    support_email = models.EmailField(
        'Email поддержки',
        blank=True,
    )
    returns_email = models.EmailField(
        'Email для возвратов',
        blank=True,
    )
    shipping_enabled = models.BooleanField(
        'Доставка СДЭК включена',
        default=False,
    )
    pickup_enabled = models.BooleanField(
        'Самовывоз включён',
        default=False,
    )

    class Meta:
        verbose_name = 'настройки магазина'
        verbose_name_plural = 'настройки магазинов'
