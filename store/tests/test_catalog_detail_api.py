from decimal import Decimal

import pytest
from rest_framework import status

from store.tests.assertions import (
    assert_catalog_merch_detail_contract,
    assert_catalog_release_detail_contract,
)
from store.tests.factories import MerchKindFactory
from store.tests.scenarios import (
    create_album_product,
    create_carrier_product,
    create_merch_product,
)

pytestmark = pytest.mark.django_db


class TestCatalogReleaseDetail:
    """Тесты detail-ручки релиза."""

    def test_catalog_release_detail_has_expected_values(
        self,
        api_client,
        catalog_release_detail_url,
    ):
        """Detail релиза содержит ожидаемые данные альбома."""
        product = create_album_product(
            name='Digital Album',
            artist_name='Test Artist',
        )
        album = product.album

        response = api_client.get(catalog_release_detail_url(album))

        assert response.status_code == status.HTTP_200_OK
        assert_catalog_release_detail_contract(response.data)

        assert response.data['id'] == album.id
        assert response.data['artist_name'] == album.owner.artist_profile.name
        assert response.data['is_single'] == album.is_single

    def test_catalog_release_detail_contains_album_and_carrier_variants(
        self,
        api_client,
        catalog_release_detail_url,
    ):
        """Detail релиза содержит цифровой вариант и варианты носителей."""
        album_product = create_album_product(
            name='Digital Album',
            artist_name='Test Artist',
            price=Decimal('199.00'),
        )
        cd_kind = MerchKindFactory(
            name='CD',
            slug='cd',
            is_carrier=True,
        )
        vinyl_kind = MerchKindFactory(
            name='Винил',
            slug='vinyl',
            is_carrier=True,
        )

        cd_product = create_carrier_product(
            name='Digital Album CD',
            album=album_product.album,
            kind=cd_kind,
            price=Decimal('990.00'),
        )
        vinyl_product = create_carrier_product(
            name='Digital Album Vinyl',
            album=album_product.album,
            kind=vinyl_kind,
            price=Decimal('2490.00'),
        )

        response = api_client.get(
            catalog_release_detail_url(album_product.album),
        )

        assert response.status_code == status.HTTP_200_OK
        assert_catalog_release_detail_contract(response.data)

        variant_ids = {
            item['variant_id'] for item in response.data['variants']
        }

        assert variant_ids == {
            album_product.variants.first().id,
            cd_product.variants.first().id,
            vinyl_product.variants.first().id,
        }


class TestCatalogMerchDetail:
    """Тесты detail-ручки обычного мерча."""

    def test_catalog_merch_detail_has_expected_values(
        self,
        api_client,
        catalog_merch_detail_url,
    ):
        """Detail обычного мерча содержит ожидаемые данные и варианты."""
        kind = MerchKindFactory(
            name='Футболка',
            slug='tshirt',
            is_carrier=False,
        )
        product = create_merch_product(
            name='Tour Tee',
            artist_name='Test Artist',
            kind=kind,
            price=Decimal('1890.00'),
        )
        merch = product.merch
        variant = product.variants.first()

        response = api_client.get(catalog_merch_detail_url(merch))

        assert response.status_code == status.HTTP_200_OK
        assert_catalog_merch_detail_contract(response.data)

        assert response.data['id'] == merch.id
        assert response.data['name'] == merch.name
        assert response.data['description'] == merch.description
        assert response.data['price'] == float(product.price)
        assert response.data['allow_overpay'] == product.allow_overpay
        assert response.data['kind'] == kind.name
        assert response.data['property_name'] == product.property_name
        assert response.data['stock'] == variant.stock
        assert response.data['artist_name'] == merch.owner.artist_profile.name
        assert response.data['images'] == []

        assert response.data['variants'] == [
            {
                'sku': variant.sku,
                'stock': variant.stock,
                'variant_id': variant.id,
                'property_value': variant.property_value,
            },
        ]
