from django.db import models

from ..abstract import TimestampModel


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

    class Meta:
        verbose_name = 'настройки магазина'
        verbose_name_plural = 'настройки магазинов'
