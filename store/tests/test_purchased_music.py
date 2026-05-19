"""Тесты API купленной музыки слушателя."""

from decimal import Decimal

import pytest
from rest_framework import status

from store.models import Album, Order, OrderItem, Track

pytestmark = pytest.mark.django_db


class TestPurchasedMusicAPI:
    """Набор тестов для проверки библиотеки купленной музыки."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        listener_client,
        purchased_music_url,
        variant_factory,
    ) -> None:
        """Автоматически прокидывает зависимости в self перед каждым тестом."""
        self.listener_client = listener_client
        self.purchased_music_url = purchased_music_url
        self.variant_factory = variant_factory

    def create_paid_order(
        self,
        listener_user,
        variants,
        order_status=Order.Status.PAID,
    ):
        """Создает оплаченный заказ с переданными вариантами товаров."""
        order = Order.objects.create(
            user=listener_user,
            status=order_status,
            total=Decimal('666.00'),
        )

        for variant in variants:
            OrderItem.objects.create(
                order=order,
                product_variant=variant,
                price_at_purchase=variant.product.price,
                unit_price=variant.product.price,
                quantity=1,
                product_info={'name': str(variant.product)},
            )

        return order

    def test_purchased_music_returns_full_album(self, listener_user):
        """Купленный целиком альбом попадает в список альбомов."""
        album_variant = self.variant_factory('album', name='Purchased Album')
        album = album_variant.product.album

        Track.objects.create(name='Track 1', owner=album.owner, album=album)
        Track.objects.create(name='Track 2', owner=album.owner, album=album)

        self.create_paid_order(listener_user, [album_variant])

        response = self.listener_client.get(self.purchased_music_url)

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['albums']] == [album.id]
        assert response.data['tracks'] == []

    def test_purchased_music_returns_single_track(self, listener_user):
        """Отдельно купленный трек попадает в список треков."""
        track_variant = self.variant_factory('track', name='Single Track')
        track = track_variant.product.track
        self.variant_factory(
            'track',
            name='Second Track',
            album=track.album,
        )

        self.create_paid_order(listener_user, [track_variant])

        response = self.listener_client.get(self.purchased_music_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['albums'] == []
        assert [item['id'] for item in response.data['tracks']] == [track.id]

    def test_purchased_music_does_not_return_partial_album(
        self,
        listener_user,
    ):
        """Частично купленный альбом не попадает в список альбомов."""
        owner = self.variant_factory('album').product.album.owner
        album = Album.objects.create(name='Partial Album', owner=owner)

        bought_track_variant = self.variant_factory(
            'track',
            name='Bought Track',
            album=album,
        )
        bought_track = bought_track_variant.product.track

        Track.objects.create(
            name='Not Bought Track',
            owner=album.owner,
            album=album,
        )

        self.create_paid_order(listener_user, [bought_track_variant])

        response = self.listener_client.get(self.purchased_music_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['albums'] == []
        assert [item['id'] for item in response.data['tracks']] == [
            bought_track.id,
        ]

    def test_purchased_music_does_not_return_other_user_purchase(
        self,
        user_factory,
    ):
        """Покупки другого пользователя не попадают в библиотеку."""
        other_user = user_factory()
        track_variant = self.variant_factory('track', name='Other User Track')

        self.create_paid_order(other_user, [track_variant])

        response = self.listener_client.get(self.purchased_music_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'albums': [],
            'tracks': [],
        }
