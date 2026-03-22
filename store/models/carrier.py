"""Модуль справочника типов носителей."""

from django.db import models

from store.constants import MAX_CHAR_LENGTH
from users.models.abstract import ActivatableModel


class Carrier(ActivatableModel):
    """Модель носителя (CD, Vinyl, Digital и т.д.).

    Классифицирует типы изданий музыкального контента.
    """

    name = models.CharField(
        'Название',
        max_length=MAX_CHAR_LENGTH,
        unique=True,
        help_text='Тип носителя',
    )
    slug = models.SlugField(
        'Слаг',
        max_length=MAX_CHAR_LENGTH,
        unique=True,
        help_text='Разрешены только буквы, цифры, дефисы и подчеркивания.'
        ' Должен быть уникальным.',
    )

    class Meta:
        verbose_name = 'носитель'
        verbose_name_plural = 'носители'
        ordering = ('name',)

    def __str__(self):
        return self.name
