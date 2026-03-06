from django.contrib.auth import get_user_model
from django.db import models

from . import BaseRelease
from ..constants import MAX_STR_LENGHT

User = get_user_model()


class Single(BaseRelease):
    """Сингл артиста."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='single',
        verbose_name='Пользователь'
    )

    class Meta:
        verbose_name = 'сингл'
        verbose_name_plural = 'Синглы'

    def __str__(self):
        return self.name[:MAX_STR_LENGHT]
