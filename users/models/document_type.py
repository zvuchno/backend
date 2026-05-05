"""Модуль модели типов дукументов."""

from django.db import models

from users.constants import MAX_CHAR_LENGTH, MAX_SLUG_LENGTH


class DocumentType(models.Model):
    """Тип юридического документа."""

    name = models.CharField(
        'Название документа',
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
        verbose_name = 'тип документа'
        verbose_name_plural = 'типы документов'
        ordering = ('name',)

    def __str__(self):
        return self.name
