from django.db import models

from ..constants import MAX_CHAR_LENGTH, MAX_STR_LENGHT


class Genre(models.Model):
    """Жанр музыкального релиза."""

    name = models.CharField(
        'Название жанра',
        unique=True,
        max_length=MAX_CHAR_LENGTH)

    class Meta:
        verbose_name = 'жанр'
        verbose_name_plural = 'Жанры'

    def __str__(self):
        return self.name[:MAX_STR_LENGHT]
