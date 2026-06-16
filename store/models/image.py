from django.db import models
from django.db.models import Q

from common.storages import get_public_media_storage

from store.models.merch import Merch
from store.upload_paths import merch_image_upload_to
from store.validators import validate_file_size
from users.models.abstract import ActivatableModel, TimestampModel


class Image(ActivatableModel, TimestampModel):
    """Фото/Изображение мерча."""

    merch = models.ForeignKey(
        Merch,
        on_delete=models.CASCADE,
        related_name='images_merch',
        verbose_name='Мерч',
    )
    image = models.ImageField(
        'Фото',
        upload_to=merch_image_upload_to,
        storage=get_public_media_storage,
        validators=(validate_file_size,),
    )
    is_main = models.BooleanField('Главное фото', default=False)

    class Meta:
        verbose_name = 'фото мерча'
        verbose_name_plural = 'фотографии мерча'
        constraints = [
            models.UniqueConstraint(
                fields=['merch'],
                condition=Q(is_main=True),
                name='unique_main_image_per_merch',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_main:
            Image.objects.filter(
                merch=self.merch,
                is_main=True,
            ).update(is_main=False)
        super().save(*args, **kwargs)
