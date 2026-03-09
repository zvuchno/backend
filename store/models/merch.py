from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from users.models.abstract import ActivatableModel, TimestampModel

from ..constants import (
    NAME_MERCH_MAX_LENGTH,
    DESCRIPTION_MERCH_MAX_LENGTH,
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACEC,
    VISIBILITY_MAX_LENGTH,
    DEFAULT_QUANTITY,
)
from .album import Album
from .category import Category


User = get_user_model()


class Type(ActivatableModel, TimestampModel):
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
            while Type.objects.filter(
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


class Property(ActivatableModel, TimestampModel):
    """Свойства мерча."""
    name = models.CharField('Название', max_length=NAME_MERCH_MAX_LENGTH)
    property = models.CharField('Свойство', max_length=NAME_MERCH_MAX_LENGTH)
    sku = models.CharField(
        'Идентефикатор товара', max_length=NAME_MERCH_MAX_LENGTH,
        blank=True, null=True
    )
    quantity = models.PositiveIntegerField('Количество')

    class Meta:
        verbose_name = 'Свойство мерча'
        verbose_name_plural = 'Свойства мерча'

    def __str__(self):
        return self.name


class Merch(ActivatableModel, TimestampModel):
    """Модель мерча."""

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Опубликовано'
        LINK_ONLY = 'link_only', 'Доступно по ссылке'
        HIDDEN = 'hidden', 'Скрыто'

    category = models.ForeignKey(Category, on_delete=models.SET_NULL,
                                 related_name='merch',
                                 verbose_name='Категория',
                                 null=True)
    name = models.CharField(
        'Название', max_length=NAME_MERCH_MAX_LENGTH
    )
    price = models.DecimalField(
        'Цена', max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACEC,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00')
    )
    access_price_more = models.BooleanField(
        'Разрешение платить больше', default=False
    )
    quantity = models.PositiveIntegerField(
        'Количество', default=DEFAULT_QUANTITY
    )
    type = models.ForeignKey(
        Type, on_delete=models.SET_NULL,
        verbose_name='Тип', related_name='merch',
        null=True
    )
    description = models.TextField(
        'Описание', max_length=DESCRIPTION_MERCH_MAX_LENGTH,
        null=True, blank=True
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name='Автор'
    )
    visibility = models.CharField(
        'Приватность', choices=Visibility.choices,
        default=Visibility.PUBLIC,
        max_length=VISIBILITY_MAX_LENGTH
    )
    property = models.ManyToManyField(
        Property, blank=True,
        verbose_name='Свойства', related_name='merch'
    )
    album = models.ManyToManyField(Album, blank=True,
                                   verbose_name='Альбом', related_name='merch')

    class Meta:
        verbose_name = 'Мерч'
        verbose_name_plural = 'Мерчи'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Image(ActivatableModel, TimestampModel):
    """Фото/Изображение мерча."""
    merch = models.ForeignKey(Merch, on_delete=models.CASCADE,
                              related_name='images_merch', verbose_name='Мерч')
    image = models.ImageField('Фото', upload_to='photos_merch/',
                              blank=True, null=True)

    class Meta:
        verbose_name = 'Фото мерча'
        verbose_name_plural = 'Фотографии мерча'
