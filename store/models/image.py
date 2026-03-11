from django.db import models

from users.models.abstract import ActivatableModel, TimestampModel
from store.models import Merch


class Image(ActivatableModel, TimestampModel):
    """Фото/Изображение мерча."""
    merch = models.ForeignKey(Merch, on_delete=models.CASCADE,
                              related_name='images_merch', verbose_name='Мерч')
    image = models.ImageField('Фото', upload_to='photos_merch/')

    class Meta:
        verbose_name = 'Фото мерча'
        verbose_name_plural = 'Фотографии мерча'
