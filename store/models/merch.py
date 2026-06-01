from django.db import models

from store.models.abstract.base_content import BaseContent
from store.models.abstract.visibility_model import VisibilityModel
from store.models.album import Album
from store.models.merch_kind import MerchKind
from store.querysets.visibility import VisibilityQuerySet


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

    @property
    def is_carrier(self):
        """Возвращает True, если тип мерча является носителем."""
        return self.kind is not None and self.kind.is_carrier

    objects = VisibilityQuerySet.as_manager()

    class Meta:
        verbose_name = 'мерч'
        verbose_name_plural = 'мерчи'
        ordering = ('name',)

    def __str__(self):
        return self.name
