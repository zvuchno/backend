from django.db import models
from django.utils.text import slugify

from users.models.abstract import ActivatableModel, TimestampModel

from store.constants import NAME_MERCH_MAX_LENGTH


class Kind(ActivatableModel, TimestampModel):
    """Тип мерча."""
    name = models.CharField(
        'Название', max_length=NAME_MERCH_MAX_LENGTH
    )
    slug = models.SlugField(
        'slug', max_length=NAME_MERCH_MAX_LENGTH, unique=True
    )

    def save(self, *args, **kwargs):
        """Получение слага при его отсутствии"""
        if not self.slug:
            slug = slugify(self.name)
            new_slug = slug
            counter = 1
            while Kind.objects.filter(
                slug=new_slug
            ).exclude(pk=self.pk).exists():
                new_slug = f'{slug}-{counter}'
                counter += 1
            self.slug = new_slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Тип мерча'
        verbose_name_plural = 'Типы мерча'

    def __str__(self):
        return self.name
