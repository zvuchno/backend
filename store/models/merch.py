from django.contrib.auth import get_user_model
from django.db import models

from store.models.abstract.base_content import BaseContent
from store.models.abstract.visibility_model import VisibilityModel
from store.models.album import Album
from store.models.merch_kind import MerchKind

User = get_user_model()


class Merch(BaseContent, VisibilityModel):
    """Модель мерча."""

    kind = models.ForeignKey(
        MerchKind,
        on_delete=models.SET_NULL,
        verbose_name='Тип',
        related_name='merch',
        null=True,
    )
    album = models.ForeignKey(
        Album,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Альбом',
        related_name='merch',
    )

    is_carrier = models.BooleanField('Носитель', default=False)

    class Meta:
        verbose_name = 'мерч'
        verbose_name_plural = 'мерчи'
        ordering = ('name',)

    def __str__(self):
        return self.name
