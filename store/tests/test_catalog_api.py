import pytest
from rest_framework import status

from store.tests.scenarios import (
    create_catalog_type_dataset,
    create_catalog_visibility_dataset,
    get_product_ids,
)

pytestmark = pytest.mark.django_db


def test_catalog_returns_only_public_products(api_client, catalog_url):
    """Каталог возвращает только видимы и опубликованные товары."""
    products = create_catalog_visibility_dataset()

    response = api_client.get(catalog_url)

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['public_merch'].id,
        products['public_album'].id,
    }


def test_catalog_filters_album_products(api_client, catalog_url):
    """Каталог фильтрует товары по типу album."""
    products = create_catalog_type_dataset()

    response = api_client.get(catalog_url, {'type': 'album'})

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['album'].id,
    }


def test_catalog_filters_merch_products(api_client, catalog_url):
    """Фильтр type=merch возвращает весь мерч, включая носители."""
    products = create_catalog_type_dataset()

    response = api_client.get(catalog_url, {'type': 'merch'})

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['merch'].id,
        products['carrier'].id,
    }


def test_catalog_returns_all_product_types_by_default(api_client, catalog_url):
    """Каталог по умолчанию возвращает все публичные типы товаров."""
    products = create_catalog_type_dataset()

    response = api_client.get(catalog_url)

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['album'].id,
        products['merch'].id,
        products['carrier'].id,
    }
