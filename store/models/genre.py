from django.db import models

from ..constants import MAX_CHAR_LENGTH, MAX_SLUG_LENGTH, MAX_STR_LENGTH


class Genre(models.Model):
    """Жанр музыкального релиза."""

    name = models.CharField(
        'Название жанра',
        unique=True,
        max_length=MAX_CHAR_LENGTH,
    )
    slug = models.SlugField(
        'Слаг',
        unique=True,
        max_length=MAX_SLUG_LENGTH,
        help_text='Разрешены только буквы, цифры, дефисы и подчеркивания.'
        ' Должен быть уникальным.',
    )

    class Meta:
        verbose_name = 'жанр'
        verbose_name_plural = 'Жанры'
        ordering = ('name',)

    def __str__(self):
        return self.name[:MAX_STR_LENGTH]
