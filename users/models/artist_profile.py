from django.conf import settings
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.db import models
from slugify import slugify

from phonenumber_field.modelfields import PhoneNumberField

from .abstract import ActivatableModel, TimestampModel
# TODO перенести эти константы в core, но потом.
from ..constants import (
    ARTIST_NAME_FIELD_MAX_LENGTH, ARTIST_NAME_FIELD_MIN_LENGTH,
    ARTIST_DESC_FIELD_MAX_LENGTH, ARTIST_DESC_FIELD_MIN_LENGTH,
    CITY_FIELD_MAX_LENGTH, CITY_FIELD_MIN_LENGTH,
)


class ArtistProfile(ActivatableModel, TimestampModel):
    """Модель артиста."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='artist_profile',
        verbose_name='Профиль артиста',
    )
    name = models.CharField(
        'Имя артиста',
        max_length=ARTIST_NAME_FIELD_MAX_LENGTH,
        validators=[MinLengthValidator(ARTIST_NAME_FIELD_MIN_LENGTH)],
    )
    slug = models.SlugField(
        'slug',
        unique=True,
        blank=True,
        max_length=ARTIST_NAME_FIELD_MAX_LENGTH,
    )
    phone = PhoneNumberField('Номер телефона', blank=True)
    city = models.CharField(
        'Город',
        max_length=CITY_FIELD_MAX_LENGTH,
        blank=True,
        validators=[MinLengthValidator(CITY_FIELD_MIN_LENGTH)],
    )
    url = models.URLField('URL', blank=True)
    description = models.TextField(
        'Об исполнителе',
        blank=True,
        validators=[
            MinLengthValidator(ARTIST_DESC_FIELD_MIN_LENGTH),
            MaxLengthValidator(ARTIST_DESC_FIELD_MAX_LENGTH),
        ],
    )
    cover = models.ImageField(
        'Обложка',
        upload_to='artists/covers',
        blank=True,
    )

    def save(self, *args, **kwargs):
        """Переопределено сохранение, чтобы гарантированно получить slug."""
        if not self.slug:
            slug = slugify(self.name)
            new_slug = slug
            slug_counter = 1
            while ArtistProfile.objects.filter(slug=new_slug).exclude(
                pk=self.pk
            ).exists():
                new_slug = f'{slug}-{slug_counter}'
                slug_counter += 1
            self.slug = new_slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Артист'
        verbose_name_plural = 'артисты'
        ordering = ['name']

    def __str__(self):
        return self.name
