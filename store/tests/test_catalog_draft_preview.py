from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from store.tests.factories import MerchKindFactory
from store.tests.scenarios import (
    create_album_product,
    create_carrier_product,
    create_merch_product,
    get_product_ids,
)
from users.tests.factories import ArtistProfileFactory, UserFactory

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures('publication_readiness_disabled'),
]


@pytest.mark.parametrize(
    ('mode', 'role', 'visible'),
    [
        ('off', 'staff', False),
        ('staff', 'anonymous', False),
        ('staff', 'user', False),
        ('staff', 'staff', True),
        ('all', 'anonymous', True),
        ('all', 'user', True),
        ('all', 'staff', True),
    ],
)
def test_draft_preview_in_catalog_and_details(
    api_client,
    catalog_url,
    catalog_release_detail_url,
    catalog_merch_detail_url,
    mode,
    role,
    visible,
):
    """Черновики видны только сотруднику при включённом предпросмотре."""
    artist = ArtistProfileFactory(user=None)

    album_product = create_album_product(
        artist=artist,
        is_published=False,
        price=Decimal('0.00'),
    )
    merch_product = create_merch_product(
        artist=artist,
        is_published=False,
        price=Decimal('0.00'),
    )

    album = album_product.album
    album.release_date = timezone.localdate() + timedelta(days=30)
    album.save(update_fields=('release_date',))

    merch_product.variants.update(stock=0)

    assert album.payout_recipient_id is None
    assert merch_product.merch.payout_recipient_id is None

    if role != 'anonymous':
        api_client.force_authenticate(
            user=UserFactory(is_staff=role == 'staff'),
        )

    with override_settings(CATALOG_DRAFT_PREVIEW_MODE=mode):
        catalog_response = api_client.get(catalog_url)
        album_response = api_client.get(
            catalog_release_detail_url(album),
        )
        merch_response = api_client.get(
            catalog_merch_detail_url(merch_product.merch),
        )

    assert catalog_response.status_code == status.HTTP_200_OK

    product_ids = set(get_product_ids(catalog_response))

    assert (album_product.id in product_ids) is visible
    assert (merch_product.id in product_ids) is visible

    expected_status = (
        status.HTTP_200_OK if visible else status.HTTP_404_NOT_FOUND
    )
    assert album_response.status_code == expected_status
    assert merch_response.status_code == expected_status

    if visible:
        assert album_response.data['variants']
        assert merch_response.data['variants']

        assert all(
            variant['is_available_for_purchase'] is False
            for variant in album_response.data['variants']
        )
        assert all(
            variant['is_available_for_purchase'] is False
            for variant in merch_response.data['variants']
        )


def test_draft_preview_does_not_allow_cart(
    api_client,
    cart_add_url,
):
    """Даже сотрудник не может купить черновик через предпросмотр."""
    product = create_merch_product(is_published=False)
    variant = product.variants.first()

    api_client.force_authenticate(user=UserFactory(is_staff=True))

    with override_settings(CATALOG_DRAFT_PREVIEW_MODE='staff'):
        response = api_client.post(
            cart_add_url,
            data={
                'product_variant': variant.id,
                'quantity': 1,
            },
            format='json',
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert variant.is_available_for_purchase is False


def test_draft_carrier_visible_inside_release_only_in_preview(
    api_client,
    catalog_release_detail_url,
):
    """Неопубликованный носитель появляется в деталке релиза лишь для staff."""
    album_product = create_album_product()
    carrier_product = create_carrier_product(album=album_product.album)

    carrier = carrier_product.merch
    carrier.is_published = False
    carrier.save(update_fields=('is_published',))

    carrier_variant_id = carrier_product.variants.first().id
    url = catalog_release_detail_url(album_product.album)

    with override_settings(CATALOG_DRAFT_PREVIEW_MODE='staff'):
        public_response = api_client.get(url)

        api_client.force_authenticate(user=UserFactory(is_staff=True))
        staff_response = api_client.get(url)

    assert public_response.status_code == status.HTTP_200_OK
    assert staff_response.status_code == status.HTTP_200_OK

    public_variant_ids = {
        item['variant_id'] for item in public_response.data['variants']
    }
    staff_variants = {
        item['variant_id']: item for item in staff_response.data['variants']
    }

    assert carrier_variant_id not in public_variant_ids
    assert carrier_variant_id in staff_variants
    assert (
        staff_variants[carrier_variant_id]['is_available_for_purchase']
        is False
    )


@pytest.mark.parametrize(
    ('params', 'expected_type'),
    [
        ({'type': 'album'}, 'album'),
        ({'type': 'merch'}, 'merch'),
        ({'kind': 'test-kind'}, 'merch'),
    ],
)
def test_draft_preview_catalog_filters(
    api_client,
    catalog_url,
    params,
    expected_type,
):
    """Фильтры каталога работают с черновиками."""
    kind = MerchKindFactory(slug='test-kind')
    album_product = create_album_product(is_published=False)
    merch_product = create_merch_product(
        kind=kind,
        is_published=False,
    )

    api_client.force_authenticate(user=UserFactory(is_staff=True))

    with override_settings(CATALOG_DRAFT_PREVIEW_MODE='staff'):
        response = api_client.get(catalog_url, params)

    assert response.status_code == status.HTTP_200_OK

    expected_id = (
        album_product.id if expected_type == 'album' else merch_product.id
    )
    assert set(get_product_ids(response)) == {expected_id}
