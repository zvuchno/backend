from decimal import Decimal

import pytest
from rest_framework import status

from store.tests.scenarios import (
    create_album_product,
    create_carrier_product,
    create_catalog_date_sorting_dataset,
    create_catalog_filter_dataset,
    create_catalog_type_dataset,
    create_catalog_visibility_dataset,
    create_merch_product,
    get_product_ids,
)

pytestmark = pytest.mark.django_db


def get_catalog_cards(response):
    """Возвращает карточки каталога из paginated-ответа."""
    assert response.status_code == status.HTTP_200_OK, response.data
    assert 'results' in response.data, response.data
    return response.data['results']


def get_catalog_card_by_product_id(response, product_id):
    """Возвращает карточку каталога по Product.id."""
    for card in get_catalog_cards(response):
        if card['product_id'] == product_id:
            return card

    raise AssertionError(
        f'Карточка товара product_id={product_id} не найдена.',
    )


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


def test_catalog_returns_all_product_types_with_all_type(
    api_client,
    catalog_url,
):
    """Фильтр type=all возвращает альбомы, обычный мерч и носители."""
    products = create_catalog_type_dataset()

    response = api_client.get(catalog_url, {'type': 'all'})

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['album'].id,
        products['merch'].id,
        products['carrier'].id,
    }


def test_catalog_album_card_has_expected_values(api_client, catalog_url):
    """Карточка альбома содержит ожидаемые значения."""
    product = create_album_product(
        name='Digital Album',
        artist_name='Test Artist',
        price=Decimal('1000.00'),
    )
    variant = product.variants.first()
    album = product.album

    response = api_client.get(catalog_url)

    card = get_catalog_card_by_product_id(response, product.id)

    assert card['product_id'] == product.id
    assert card['name'] == album.name
    assert card['artist_name'] == album.owner.artist_profile.name
    assert card['kind'] == 'Альбом'
    assert card['year'] == album.release_date.year
    assert card['price'] == str(product.price)
    assert card['image'] is None
    assert card['is_favorite'] is False
    assert card['target'] == {
        'type': 'release',
        'url': f'/api/v1/store/catalog/release/{album.id}/',
        'selected_variant_id': variant.id,
    }


def test_catalog_merch_card_has_expected_values(api_client, catalog_url):
    """Карточка обычного мерча содержит ожидаемые значения."""
    product = create_merch_product(
        name='Cap',
        artist_name='Test Artist',
        price=Decimal('500.00'),
    )
    merch = product.merch

    response = api_client.get(catalog_url)

    card = get_catalog_card_by_product_id(response, product.id)

    assert card['product_id'] == product.id
    assert card['name'] == merch.name
    assert card['artist_name'] == merch.owner.artist_profile.name
    assert card['kind'] == merch.kind.name
    assert card['year'] is None
    assert card['price'] == str(product.price)
    assert card['image'] is None
    assert card['is_favorite'] is False
    assert card['target'] == {
        'type': 'merch',
        'url': f'/api/v1/store/catalog/merch/{merch.id}/',
        'selected_variant_id': None,
    }


def test_catalog_carrier_card_has_expected_values(api_client, catalog_url):
    """Карточка носителя содержит значения мерча и ведет на релиз."""
    product = create_carrier_product(
        name='LP',
        artist_name='Test Artist',
        price=Decimal('10000.00'),
    )
    variant = product.variants.first()
    merch = product.merch
    album = merch.album

    response = api_client.get(catalog_url)

    card = get_catalog_card_by_product_id(response, product.id)

    assert merch.kind.is_carrier is True
    assert album is not None

    assert card['product_id'] == product.id
    assert card['name'] == merch.name
    assert card['artist_name'] == merch.owner.artist_profile.name
    assert card['kind'] == merch.kind.name
    assert card['year'] == album.release_date.year
    assert card['price'] == str(product.price)
    assert card['image'] is None
    assert card['is_favorite'] is False
    assert card['target'] == {
        'type': 'release',
        'url': f'/api/v1/store/catalog/release/{album.id}/',
        'selected_variant_id': variant.id,
    }


def test_catalog_orders_by_created_at(api_client, catalog_url):
    """Каталог сортируется по дате создания по возрастанию."""
    products = create_catalog_date_sorting_dataset()

    response = api_client.get(catalog_url, {'ordering': 'created_at'})

    assert response.status_code == status.HTTP_200_OK
    assert get_product_ids(response) == [
        products['old'].id,
        products['middle'].id,
        products['new'].id,
    ]


def test_catalog_orders_by_created_at_desc(api_client, catalog_url):
    """Каталог сортируется по дате создания по убыванию."""
    products = create_catalog_date_sorting_dataset()

    response = api_client.get(catalog_url, {'ordering': '-created_at'})

    assert response.status_code == status.HTTP_200_OK
    assert get_product_ids(response) == [
        products['new'].id,
        products['middle'].id,
        products['old'].id,
    ]


def test_catalog_random_ordering_returns_visible_products(
    api_client,
    catalog_url,
):
    """Случайная сортировка возвращает видимые товары каталога."""
    products = create_catalog_type_dataset()

    response = api_client.get(catalog_url, {'ordering': 'random'})

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['album'].id,
        products['merch'].id,
        products['carrier'].id,
    }


def test_catalog_filters_all_products_by_kind(api_client, catalog_url):
    """Фильтр kind при type=all возвращает только мерч указанного вида."""
    products = create_catalog_filter_dataset()

    response = api_client.get(
        catalog_url,
        {
            'type': 'all',
            'kind': 'tshirt',
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['tshirt_merch'].id,
    }


def test_catalog_filters_carriers_by_kind(api_client, catalog_url):
    """Фильтр kind возвращает носители указанного вида."""
    products = create_catalog_filter_dataset()

    response = api_client.get(
        catalog_url,
        {
            'type': 'all',
            'kind': 'vinyl',
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['rock_carrier'].id,
        products['jazz_carrier'].id,
    }


def test_catalog_filters_by_multiple_kinds(api_client, catalog_url):
    """Фильтр kind поддерживает несколько значений."""
    products = create_catalog_filter_dataset()

    response = api_client.get(
        catalog_url,
        {
            'kind': 'tshirt,cap',
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['tshirt_merch'].id,
        products['cap_merch'].id,
    }


def test_catalog_filters_by_genre(api_client, catalog_url):
    """Фильтр genre возвращает альбомы и носители указанного жанра."""
    products = create_catalog_filter_dataset()

    response = api_client.get(catalog_url, {'genre': 'rock'})

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['rock_album'].id,
        products['rock_carrier'].id,
    }


def test_catalog_filters_by_multiple_genres(api_client, catalog_url):
    """Фильтр genre поддерживает несколько значений."""
    products = create_catalog_filter_dataset()

    response = api_client.get(
        catalog_url,
        {
            'genre': 'rock,jazz',
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['rock_album'].id,
        products['jazz_album'].id,
        products['rock_carrier'].id,
        products['jazz_carrier'].id,
    }


def test_catalog_filters_by_artist(api_client, catalog_url):
    """Фильтр artist возвращает все товары указанного артиста."""
    products = create_catalog_filter_dataset()
    artist_slug = products['first_artist'].artist_profile.slug

    response = api_client.get(catalog_url, {'artist': artist_slug})

    assert response.status_code == status.HTTP_200_OK
    assert set(get_product_ids(response)) == {
        products['rock_album'].id,
        products['tshirt_merch'].id,
        products['rock_carrier'].id,
    }
