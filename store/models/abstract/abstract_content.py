from django.contrib.auth import get_user_model
from django.db import models

from store.constants import MAX_CHAR_LENGTH
from users.models.abstract import ActivatableModel, TimestampModel

User = get_user_model()


class AbstractContent(ActivatableModel, TimestampModel):
    """Абстрактная модель для моделей контента."""

    name = models.CharField('Название', max_length=MAX_CHAR_LENGTH)
    description = models.TextField('Описание', blank=True, default='')

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='Владелец',
    )

    class Meta:
        abstract = True
