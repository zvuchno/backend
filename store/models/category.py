from django.db import models
from users.models.abstract import ActivatableModel, TimestampModel
from django.utils.text import slugify

from ..constants import NAME_MERCH_MAX_LENGTH


class Category(ActivatableModel, TimestampModel):
    """Категории."""
    name = models.CharField(
        'Название', max_length=NAME_MERCH_MAX_LENGTH, unique=True
    )
    slug = models.SlugField(
        'slug', max_length=NAME_MERCH_MAX_LENGTH, unique=True
    )

    def save(self, *args, **kwargs):
        """Получение слага при отсутствии."""
        if not self.slug:
            slug = slugify(self.name)
            new_slug = slug
            counter = 1
            while Category.objects.filter(
                slug=new_slug
            ).exclude(pk=self.pk).exists():
                new_slug = f'{slug}-{counter}'
                counter += 1
            self.slug = new_slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name
