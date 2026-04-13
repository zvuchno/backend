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

from typing import Callable

import pytest
from django.urls import reverse

from store.models import Album, Merch, Product, ProductVariant, Track


# =================================
# Content fixtures
# =================================
@pytest.fixture
def variant_factory(user):
    """Фабрика для создания вариантов разных типов товаров."""

    def _create_variant(
        product_type='merch',
        stock=10,
        characteristic={},
        allow_overpay=True,
    ) -> Callable[..., ProductVariant]:
        if product_type == 'album':
            item = Album.objects.create(name='New Album', owner=user)
            product = Product.objects.create(album=item, price=1000)
            v_stock = None
        elif product_type == 'track':
            album = Album.objects.create(name='Track Album', owner=user)
            item = Track.objects.create(
                name='New Track',
                owner=user,
                album=album,
            )
            product = Product.objects.create(track=item, price=500)
            v_stock = None
        elif product_type == 'merch':
            item = Merch.objects.create(name='T-Shirt', owner=user)
            product = Product.objects.create(
                merch=item,
                price=1500,
                allow_overpay=allow_overpay,
            )
            v_stock = stock

        return ProductVariant.objects.create(
            product=product,
            stock=v_stock,
            characteristic=characteristic,
        )

    return _create_variant


# =================================
# URL fixtures
# =================================
@pytest.fixture
def cart_url():
    """Возвращает URL-адрес эндпоинта для корзины."""
    return reverse('api:store:cart-me')


@pytest.fixture
def cart_add_url():
    """Возвращает URL-адрес эндпоинта для добавления товара в корзину."""
    return reverse('api:store:cart-add-item')
