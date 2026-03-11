from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from users.models.abstract.timestamp_model import TimestampModel
from users.models.abstract.activatable_model import ActivatableModel


class Favorite(ActivatableModel, TimestampModel):
    """Модель избранного"""

    listener = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Слушатель',
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        verbose_name = 'избранные'
        verbose_name_plural = 'избранное'
        constraints = [
            models.constraints.UniqueConstraint(
                fields=[
                    'listener',
                    'content_type',
                    'object_id',
                ],
                name='unique_favorite_per_user',
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.content_object}'
