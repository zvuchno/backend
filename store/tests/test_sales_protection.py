from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.contrib.admin import AdminSite
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status

from store.admin.album import AlbumAdmin
from store.models import Album, Order, OrderItem, Payment
from store.services import get_release_sales_stats

pytestmark = pytest.mark.django_db


def create_order(
    user,
    variant,
    *,
    order_status=Order.Status.PAID,
    quantity=1,
):
    """Создаёт заказ с указанным вариантом товара."""
    order = Order.objects.create(
        user=user,
        status=order_status,
        total=variant.product.price * quantity,
    )

    OrderItem.objects.create(
        order=order,
        product_variant=variant,
        artist=variant.product.artist,
        payout_recipient=variant.product.payout_recipient,
        price_at_purchase=variant.product.price,
        unit_price=variant.product.price,
        quantity=quantity,
        product_info={'name': str(variant.product)},
    )

    return order


def create_purchased_release(listener_user, variant_factory):
    """Создаёт релиз с треком и прямой покупкой релиза."""
    album_variant = variant_factory(
        'album',
        name='Купленный релиз',
    )
    album = album_variant.product.album

    track_variant = variant_factory(
        'track',
        album=album,
        name='Трек релиза',
    )

    create_order(listener_user, album_variant)

    return album, track_variant.product.track


def test_artist_cannot_delete_purchased_release(
    artist_client,
    listener_user,
    variant_factory,
):
    """Артист не может удалить напрямую купленный релиз."""
    album, _ = create_purchased_release(
        listener_user,
        variant_factory,
    )

    response = artist_client.delete(
        reverse(
            'api:store:albums-detail',
            args=(album.pk,),
        ),
    )

    assert response.status_code == status.HTTP_409_CONFLICT

    album.refresh_from_db()

    assert album.is_active is True


def test_artist_can_unpublish_purchased_release(
    artist_client,
    listener_user,
    variant_factory,
):
    """Купленный релиз можно снять с публикации."""
    album, _ = create_purchased_release(
        listener_user,
        variant_factory,
    )

    response = artist_client.patch(
        reverse(
            'api:store:albums-detail',
            args=(album.pk,),
        ),
        {
            'is_published': False,
        },
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK

    album.refresh_from_db()

    assert album.is_published is False
    assert album.is_active is True


def test_artist_cannot_delete_directly_purchased_track(
    artist_client,
    listener_user,
    variant_factory,
):
    """Артист не может удалить отдельно купленный трек."""
    variant = variant_factory(
        'track',
        name='Купленный трек',
    )
    track = variant.product.track

    create_order(listener_user, variant)

    response = artist_client.delete(
        reverse(
            'api:store:tracks-detail',
            args=(track.pk,),
        ),
    )

    assert response.status_code == status.HTTP_409_CONFLICT

    track.refresh_from_db()

    assert track.is_active is True


def test_artist_cannot_delete_track_from_purchased_release(
    artist_client,
    listener_user,
    variant_factory,
):
    """Нельзя удалить трек из напрямую купленного релиза."""
    album, track = create_purchased_release(
        listener_user,
        variant_factory,
    )

    response = artist_client.delete(
        reverse(
            'api:store:tracks-detail',
            args=(track.pk,),
        ),
    )

    assert response.status_code == status.HTTP_409_CONFLICT

    track.refresh_from_db()

    assert track.is_active is True
    assert track.album_id == album.pk


def test_admin_cannot_physically_delete_purchased_release(
    listener_user,
    variant_factory,
):
    """Админ не может физически удалить напрямую купленный релиз."""
    album, _ = create_purchased_release(
        listener_user,
        variant_factory,
    )

    album_admin = AlbumAdmin(
        Album,
        AdminSite(),
    )

    with pytest.raises(ValidationError):
        album_admin.delete_model(
            Mock(),
            album,
        )

    assert Album.objects.filter(pk=album.pk).exists()


def test_successful_payment_counts_as_release_sale(
    listener_user,
    variant_factory,
):
    """Успешный платёж считается продажей до смены статуса заказа."""
    variant = variant_factory(
        'album',
        price=Decimal('500.00'),
    )
    album = variant.product.album

    order = create_order(
        listener_user,
        variant,
        order_status=Order.Status.CREATED,
        quantity=2,
    )

    Payment.objects.create(
        order=order,
        amount=Decimal('1000.00'),
        status=Payment.PaymentStatus.SUCCEEDED,
    )

    stats = get_release_sales_stats(album)

    assert stats.direct_sales == 2
