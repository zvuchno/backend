"""Фабрики тестовых объектов магазина."""

from datetime import date
from decimal import Decimal

import factory
from django.core.files.uploadedfile import SimpleUploadedFile

from store.models import (
    Album,
    Genre,
    Image,
    Merch,
    MerchKind,
    Product,
    ProductVariant,
    Track,
)
from users.tests.factories import ArtistUserFactory


class GenreFactory(factory.django.DjangoModelFactory):
    """Фабрика жанра."""

    class Meta:
        model = Genre

    name = factory.Sequence(lambda n: f'Жанр {n}')
    slug = factory.Sequence(lambda n: f'genre-{n}')


class MerchKindFactory(factory.django.DjangoModelFactory):
    """Фабрика вида мерча."""

    class Meta:
        model = MerchKind

    name = factory.Sequence(lambda n: f'Вид мерча {n}')
    slug = factory.Sequence(lambda n: f'merch-kind-{n}')
    is_carrier = False


class AlbumFactory(factory.django.DjangoModelFactory):
    """Фабрика альбома."""

    class Meta:
        model = Album

    owner = factory.SubFactory(ArtistUserFactory)
    genre = factory.SubFactory(GenreFactory)
    name = factory.Sequence(lambda n: f'Альбом {n}')
    release_date = date(2026, 1, 1)
    is_single = False
    is_published = True
    visibility = 'public'


def make_cover_file(
    name='test-cover.jpg',
    content=b'test-cover-content',
) -> SimpleUploadedFile:
    """Создает тестовый файл обложки."""
    return SimpleUploadedFile(
        name=name,
        content=content,
        content_type='image/jpeg',
    )


def make_audio_file(
    name='test-track.mp3',
    content=b'test-audio-content',
) -> SimpleUploadedFile:
    """Создает тестовый исходный аудиофайл."""
    return SimpleUploadedFile(
        name=name,
        content=content,
        content_type='audio/mpeg',
    )


class TrackFactory(factory.django.DjangoModelFactory):
    """Фабрика трека с исходным аудиофайлом."""

    class Meta:
        model = Track

    album = factory.SubFactory(AlbumFactory)
    owner = factory.LazyAttribute(lambda track: track.album.owner)
    name = factory.Sequence(lambda n: f'Трек {n}')
    position = factory.Sequence(lambda n: n + 1)
    audio_file = factory.Sequence(
        lambda n: make_audio_file(
            name=f'track-{n}.mp3',
            content=f'audio-content-{n}'.encode(),
        ),
    )


class MerchFactory(factory.django.DjangoModelFactory):
    """Фабрика мерча."""

    class Meta:
        model = Merch

    owner = factory.SubFactory(ArtistUserFactory)
    kind = factory.SubFactory(MerchKindFactory)
    name = factory.Sequence(lambda n: f'Мерч {n}')
    description = 'Тестовое описание мерча.'
    is_published = True
    visibility = 'public'


class ProductFactory(factory.django.DjangoModelFactory):
    """Базовая фабрика товара.

    Обычно в тестах лучше использовать AlbumProductFactory
    или MerchProductFactory, чтобы явно задать тип товара.
    """

    class Meta:
        model = Product

    price = Decimal('1000.00')
    allow_overpay = False
    property_name = 'Формат'


class AlbumProductFactory(ProductFactory):
    """Фабрика товара-альбома."""

    product_type = Product.ProductType.ALBUM
    album = factory.SubFactory(AlbumFactory)


class MerchProductFactory(ProductFactory):
    """Фабрика товара-мерча."""

    product_type = Product.ProductType.MERCH
    merch = factory.SubFactory(MerchFactory)
    property_name = 'Размер'


class ProductVariantFactory(factory.django.DjangoModelFactory):
    """Фабрика варианта товара."""

    class Meta:
        model = ProductVariant

    product = factory.SubFactory(AlbumProductFactory)
    sku = factory.Sequence(lambda n: f'sku-{n}')
    stock = 10
    property_value = 'default'
    is_active = True


def test_image_file(name='test-image.jpg') -> SimpleUploadedFile:
    """Создает простой тестовый файл изображения."""
    return SimpleUploadedFile(
        name=name,
        content=b'test-image-content',
        content_type='image/jpeg',
    )


class MerchImageFactory(factory.django.DjangoModelFactory):
    """Фабрика изображения мерча."""

    class Meta:
        model = Image

    merch = factory.SubFactory(MerchFactory)
    image = factory.Sequence(
        lambda n: test_image_file(name=f'merch-image-{n}.jpg'),
    )
    is_main = True
