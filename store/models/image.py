from django.db import models

from store.models.merch import Merch
from users.models.abstract import ActivatableModel, TimestampModel


class Image(ActivatableModel, TimestampModel):
    """Фото/Изображение мерча."""

    merch = models.ForeignKey(
        Merch,
        on_delete=models.CASCADE,
        related_name='images_merch',
        verbose_name='Мерч',
    )
    image = models.ImageField('Фото', upload_to='photos_merch/')

    class Meta:
        verbose_name = 'фото мерча'
        verbose_name_plural = 'фотографии мерча'
