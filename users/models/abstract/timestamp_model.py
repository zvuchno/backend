from django.db import models


class TimestampModel(models.Model):
    """Базовая абстрактная модель с временными метками."""

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
