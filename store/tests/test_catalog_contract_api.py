"""Тесты контрактов публичного API каталога."""

import pytest
from rest_framework import status

from store.models import Album, Merch, MerchKind, Product, ProductVariant
from store.tests.assertions import (
    assert_catalog_merch_detail_contract,
    assert_catalog_release_detail_contract,
    assert_public_product_card_contract,
)
from store.tests.scenarios import get_response_items

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_album_product(artist_user):
    """Создает опубликованный альбом с цифровым вариантом."""
    album = Album.objects.create(
        name='Contract Album',
        owner=artist_user,
        is_published=True,
        is_active=True,
        visibility=Album.Visibility.PUBLIC,
        is_single=False,
        description='Описание тестового альбома.',
    )
    product = Product.objects.create(
        album=album,
        price='1000.00',
        allow_overpay=True,
    )
    variant = ProductVariant.objects.create(
        product=product,
        property_value='',
        is_active=True,
    )

    return {
        'album': album,
        'product': product,
        'variant': variant,
    }


@pytest.fixture
def public_merch_product(artist_user):
    """Создает опубликованный обычный мерч с вариантом."""
    kind = MerchKind.objects.create(
        name='Футболка',
        slug='t-shirt',
        is_carrier=False,
    )
    merch = Merch.objects.create(
        name='Contract T-Shirt',
        owner=artist_user,
        kind=kind,
        is_published=True,
        is_active=True,
        visibility=Merch.Visibility.PUBLIC,
        description='Описание тестового мерча.',
    )
    product = Product.objects.create(
        merch=merch,
        price='1500.00',
        allow_overpay=False,
    )
    variant = ProductVariant.objects.create(
        product=product,
        property_value='XL',
        stock=10,
        is_active=True,
    )

    return {
        'kind': kind,
        'merch': merch,
        'product': product,
        'variant': variant,
    }


class TestCatalogListContract:
    """Тесты контракта списка публичного каталога."""

    def test_catalog_card_has_expected_contract(
        self,
        api_client,
        catalog_url,
        public_album_product,
    ):
        """Карточка каталога соответствует публичному контракту."""
        response = api_client.get(catalog_url)

        assert response.status_code == status.HTTP_200_OK

        items = get_response_items(response)
        assert len(items) == 1

        assert_public_product_card_contract(items[0])

    def test_catalog_cards_have_expected_contract_for_different_product_types(
        self,
        api_client,
        catalog_url,
        public_album_product,
        public_merch_product,
    ):
        """Карточки разных типов соответствуют одному контракту."""
        response = api_client.get(catalog_url)

        assert response.status_code == status.HTTP_200_OK

        items = get_response_items(response)
        assert len(items) == 2

        for card in items:
            assert_public_product_card_contract(card)


class TestCatalogReleaseDetailContract:
    """Тесты контракта detail-карточки релиза."""

    def test_release_detail_has_expected_contract(
        self,
        api_client,
        catalog_release_detail_url,
        public_album_product,
    ):
        """Detail релиза соответствует публичному контракту."""
        album = public_album_product['album']
        url = catalog_release_detail_url(album)

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert_catalog_release_detail_contract(response.data)


class TestCatalogMerchDetailContract:
    """Тесты контракта detail-карточки обычного мерча."""

    def test_merch_detail_has_expected_contract(
        self,
        api_client,
        catalog_merch_detail_url,
        public_merch_product,
    ):
        """Detail обычного мерча соответствует публичному контракту."""
        merch = public_merch_product['merch']
        url = catalog_merch_detail_url(merch)

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert_catalog_merch_detail_contract(response.data)
