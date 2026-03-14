from django.db import models
from django.utils.text import slugify

from store.constants import MAX_CHAR_LENGTH, MAX_SLUG_LENGTH
from users.models.abstract import ActivatableModel, TimestampModel


class Category(ActivatableModel, TimestampModel):
    """Категории."""

    name = models.CharField(
        'Название',
        max_length=MAX_CHAR_LENGTH,
        unique=True,
    )
    slug = models.SlugField(
        'slug',
        max_length=MAX_SLUG_LENGTH,
        unique=True,
    )

    def save(self, *args, **kwargs):
        """Получение слага при отсутствии."""
        if not self.slug:
            slug = slugify(self.name)
            new_slug = slug
            counter = 1
            while (
                Category.objects
                .filter(
                    slug=new_slug,
                )
                .exclude(pk=self.pk)
                .exists()
            ):
                new_slug = f'{slug}-{counter}'
                counter += 1
            self.slug = new_slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name
