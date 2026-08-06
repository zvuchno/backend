"""Абстрактная модель с признаком активности."""

from django.db import models


class ActivatableModel(models.Model):
    """Абстрактная модель с признаком активности.

    Добавляет булево поле активности и используется
    как базовый класс для сущностей, которые могут
    быть временно отключены без удаления из базы данных.
    """

    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        abstract = True
