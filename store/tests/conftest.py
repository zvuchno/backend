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

from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from store.models import (
    Album,
    Cart,
    CartItem,
    Delivery,
    Merch,
    Product,
    ProductVariant,
    Track,
)
from users.models import ConsentDocument


# =================================
# Content fixtures
# =================================
@pytest.fixture
def variant_factory(artist_user):
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
            'owner': kwargs.get('owner') or artist_user,
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
                owner=kwargs.get('owner') or artist_user,
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


@pytest.fixture
def cart_with_items(user, variant_factory) -> Cart:
    """Создает корзину с товарами (мерч и цифра)."""
    album = variant_factory('album')
    merch = variant_factory('merch')
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(
        cart=cart,
        product_variant=album,
        quantity=1,
    )
    CartItem.objects.create(
        cart=cart,
        product_variant=merch,
        quantity=1,
    )
    return cart


@pytest.fixture
def consent_doc_pdn():
    """Создает активный документ согласия на обработку ПДн."""
    return ConsentDocument.objects.create(
        document_type=ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
        version='1.0',
        content='Текст согласия для тестов...',
        is_active=True,
    )


@pytest.fixture
def consent_doc_newsletter():
    """Создает активный документ cогласия на получение рассылки."""
    return ConsentDocument.objects.create(
        document_type=ConsentDocument.DocumentType.LISTENER_NEWSLETTER,
        version='1.0',
        content='Текст согласия для тестов...',
        is_active=True,
    )


@pytest.fixture
def delivery_courier():
    """Создает активный способ доставки курьером."""
    return Delivery.objects.create(
        name='Курьерская доставка',
        delivery_type=Delivery.DeliveryType.COURIER,
        price=Decimal('500.00'),
        is_active=True,
    )


@pytest.fixture
def inactive_delivery():
    """Создает неактивный способ доставки (не должен быть доступен)."""
    return Delivery.objects.create(
        name='Старая доставка',
        delivery_type=Delivery.DeliveryType.COURIER,
        price=Decimal('100.00'),
        is_active=False,
    )


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


@pytest.fixture
def checkout_url():
    """Возвращает URL-адрес эндпоинта создания заказа."""
    return reverse('api:store:orders-checkout')


@pytest.fixture
def apply_promocode_url():
    """Возвращает URL-адрес эндпоинта применения промокода."""
    return reverse('api:store:cart-apply-promocode')


@pytest.fixture
def catalog_url():
    """Возвращает URL-адрес List эндпоинта каталога."""
    return reverse('api:store:catalog')


@pytest.fixture
def catalog_release_detail_url():
    """Возвращает URL-адрес эндпоинта детальной карточки релиза."""

    def _url(album) -> str:
        return reverse('api:store:catalog-release-detail', args=(album.id,))

    return _url


@pytest.fixture
def catalog_merch_detail_url():
    """Возвращает URL-адрес эндпоинта детальной карточки мерча."""

    def _url(merch) -> str:
        return reverse('api:store:catalog-merch-detail', args=(merch.id,))

    return _url


@pytest.fixture
def purchased_music_url():
    """Возвращает URL-адрес эндпоинта купленной музыки."""
    return reverse('api:store:purchased-music')


@pytest.fixture
def purchased_music_download_detail_url():
    """Возвращает URL detail-ручки скачивания доступного релиза."""

    def _url(album) -> str:
        return reverse(
            'api:store:purchased-music-download-detail',
            args=(album.id,),
        )

    return _url
