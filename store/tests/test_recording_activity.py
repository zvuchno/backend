"""Тесты глобальной активности мастер-записи."""

import pytest

from store.models import Product, ProductVariant
from store.tests.factories import AlbumFactory, ReleaseTrackFactory
from users.models import ArtistStoreSettings

pytestmark = pytest.mark.django_db


def test_published_tracks_excludes_inactive_recording(
    variant_factory,
):
    """Неактивная Recording исключает активное размещение из продажи."""
    active_variant = variant_factory('track')
    inactive_variant = variant_factory('track')
    active_product = active_variant.product
    inactive_product = inactive_variant.product
    inactive_track = inactive_product.track

    inactive_track.recording.is_active = False
    inactive_track.recording.save(update_fields=('is_active',))

    published_ids = set(
        Product.objects.published_tracks().values_list('pk', flat=True),
    )

    assert active_product.pk in published_ids
    assert inactive_product.pk not in published_ids
    assert inactive_track.is_active is True


def test_inactive_recording_makes_track_unavailable_for_purchase(
    ready_artist_user,
    variant_factory,
):
    """Глобальная деактивация Recording запрещает покупку трека."""
    variant = variant_factory(
        'track',
        artist=ready_artist_user.artist_profile,
    )
    recording = variant.product.track.recording

    assert variant.is_available_for_purchase is True

    recording.is_active = False
    recording.save(update_fields=('is_active',))
    variant = ProductVariant.objects.get(pk=variant.pk)

    assert variant.product.track.is_active is True
    assert variant.is_available_for_purchase is False


def test_inactive_release_track_only_disables_its_placement(
    ready_artist_user,
    variant_factory,
):
    """Деактивация ReleaseTrack не отключает другие размещения Recording."""
    first_variant = variant_factory(
        'track',
        artist=ready_artist_user.artist_profile,
    )
    first_track = first_variant.product.track
    second_release = AlbumFactory(
        artist=ready_artist_user.artist_profile,
        payout_recipient=ready_artist_user,
        created_by=ready_artist_user,
    )
    second_track = ReleaseTrackFactory(
        release=second_release,
        recording=first_track.recording,
        position=1,
    )
    second_product = Product.objects.create(
        track=second_track,
        price=500,
    )
    second_variant = ProductVariant.objects.create(
        product=second_product,
        stock=None,
    )

    first_track.is_active = False
    first_track.save(update_fields=('is_active',))
    first_variant = ProductVariant.objects.get(pk=first_variant.pk)
    second_variant = ProductVariant.objects.get(pk=second_variant.pk)

    assert first_track.recording.is_active is True
    assert first_variant.is_available_for_purchase is False
    assert second_variant.is_available_for_purchase is True

    published_ids = set(
        Product.objects.published_tracks().values_list('pk', flat=True),
    )
    assert first_variant.product_id not in published_ids
    assert second_variant.product_id in published_ids


@pytest.mark.parametrize('product_type', ['album', 'merch'])
def test_recording_activity_does_not_affect_other_product_types(
    ready_artist_user,
    variant_factory,
    product_type,
):
    """Активность Recording не влияет на товары других типов."""
    ArtistStoreSettings.objects.update_or_create(
        artist=ready_artist_user.artist_profile,
        defaults={'shipping_enabled': True},
    )
    track_variant = variant_factory(
        'track',
        artist=ready_artist_user.artist_profile,
    )
    other_variant = variant_factory(
        product_type,
        artist=ready_artist_user.artist_profile,
    )

    assert other_variant.is_available_for_purchase is True

    recording = track_variant.product.track.recording
    recording.is_active = False
    recording.save(update_fields=('is_active',))
    other_variant = ProductVariant.objects.get(pk=other_variant.pk)

    assert other_variant.is_available_for_purchase is True
