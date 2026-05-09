"""Фикстуры тестов для приложения store.

Модуль содержит набор переиспользуемых pytest-фикстур,
специфичных для данного приложения.

Используется для:
- создания тестовых объектов (модели, пользователи и т.д.);
- подготовки состояния базы данных;
- генерации входных данных для тестов;
- упрощения и устранения дублирования в тестах.

Файл не требует явного импорта — pytest находит его автоматически.
"""

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from store.models import Album, Merch, Product, ProductVariant, Track


# =================================
# Content fixtures
# =================================
@pytest.fixture
def variant_factory(user):
    """Фабрика для создания ProductVariant с разными типами продуктов."""

    def create_variant(
        product_type='merch',
        *,
        is_active=True,
        is_published=True,
        visibility='public',
        stock=10,
        property_value='',
        allow_overpay=True,
        price=None,
        **kwargs,
    ) -> ProductVariant:

        common_fields = {
            'owner': user,
            'is_active': is_active,
            'is_published': is_published,
            'visibility': visibility,
        }

        if product_type == 'album':
            item = Album.objects.create(
                name=kwargs.get('name', 'Album'),
                **common_fields,
            )
            product = Product.objects.create(album=item, price=price or 1000)
            stock_value = None

        elif product_type == 'track':
            album = kwargs.get('album') or Album.objects.create(
                name='Track Album',
                **common_fields,
            )
            item = Track.objects.create(
                name=kwargs.get('name', 'Track'),
                owner=user,
                album=album,
                audio_file=ContentFile(
                    b'fake mp3 content',
                    name='test_track.mp3',
                ),
            )
            product = Product.objects.create(track=item, price=price or 500)
            stock_value = None

        elif product_type == 'merch':
            item = Merch.objects.create(
                name=kwargs.get('name', 'T-Shirt'),
                **common_fields,
            )
            product = Product.objects.create(
                merch=item,
                price=price or 1500,
                allow_overpay=allow_overpay,
            )
            stock_value = stock
        else:
            raise ValueError(f'Unknown product_type: {product_type}')

        return ProductVariant.objects.create(
            product=product,
            stock=stock_value,
            property_value=property_value,
        )

    return create_variant


# =================================
# URL fixtures
# =================================
@pytest.fixture
def album_list_url():
    """Возвращает URL-адрес эндпоинта для списка альбомов."""
    return reverse('api:store:albums-list')


@pytest.fixture
def track_list_url():
    """Возвращает URL-адрес эндпоинта для списка треков."""
    return reverse('api:store:tracks-list')


@pytest.fixture
def cart_url():
    """Возвращает URL-адрес эндпоинта для корзины."""
    return reverse('api:store:cart-me')


@pytest.fixture
def cart_add_url():
    """Возвращает URL-адрес эндпоинта для добавления товара в корзину."""
    return reverse('api:store:cart-add-item')


@pytest.fixture
def favorites_url():
    """Возвращает URL-адрес эндпоинта избранного."""
    return reverse('api:store:me-favorites-list')
