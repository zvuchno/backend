"""Модуль содержит абстрактную модель VisibilityModel.

Используется как базовая модель для управления видимостью объектов
в других моделях проекта.
"""

from django.db import models


class VisibilityModel(models.Model):
    """Абстрактная модель для управления видимостью и статусом публикации."""

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Для всех'
        LINK_ONLY = 'link_only', 'Доступно по ссылке'
        HIDDEN = 'hidden', 'Скрыто'

    visibility = models.CharField(
        'Приватность',
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )

    is_published = models.BooleanField(
        'Опубликовано',
        default=False,
        help_text='Если включено, объект виден пользователям.',
    )

    class Meta:
        abstract = True
