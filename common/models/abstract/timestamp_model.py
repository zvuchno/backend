"""Абстрактная модель с временными метками."""

from django.db import models


class TimestampModel(models.Model):
    """Абстрактная модель с датой создания и обновления.

    Добавляет служебные поля с временными метками и используется
    как примесь для моделей, которым важно хранить время создания
    и последнего изменения записи.
    """

    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        'Дата обновления',
        auto_now=True,
    )

    class Meta:
        abstract = True
