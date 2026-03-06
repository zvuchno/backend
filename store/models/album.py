from django.contrib.auth import get_user_model
from django.db import models

from . import BaseRelease
from ..constants import MAX_STR_LENGHT

User = get_user_model()


class Album(BaseRelease):
    """Музыкальный альбом артиста."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='albums',
        verbose_name='Пользователь'
    )

    class Meta:
        verbose_name = 'альбом'
        verbose_name_plural = 'Альбомы'

    def __str__(self):
        return self.name[:MAX_STR_LENGHT]
