"""Тесты API доступной музыки слушателя."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework import status

from store.models import Album, AlbumArchive, Order, OrderItem, Track

pytestmark = pytest.mark.django_db


def get_results(response):
    """Возвращает список элементов из ответа с учетом пагинации."""
    if isinstance(response.data, dict) and 'results' in response.data:
        return response.data['results']

    return response.data


class TestPurchasedMusicAPI:
    """Набор тестов для проверки библиотеки доступной музыки."""

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
        """Купленный целиком альбом попадает в список доступных релизов."""
        album_variant = self.variant_factory('album', name='Purchased Album')
        album = album_variant.product.album

        Track.objects.create(name='Track 1', owner=album.owner, album=album)
        Track.objects.create(name='Track 2', owner=album.owner, album=album)

        self.create_paid_order(listener_user, [album_variant])

        response = self.listener_client.get(self.purchased_music_url)
        results = get_results(response)

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in results] == [album.id]
        assert results[0]['is_fully_available'] is True

    def test_purchased_music_returns_release_for_single_track(
        self,
        listener_user,
    ):
        """Отдельно купленный трек возвращает релиз с частичным доступом."""
        track_variant = self.variant_factory('track', name='Single Track')
        track = track_variant.product.track

        self.variant_factory(
            'track',
            name='Second Track',
            album=track.album,
        )

        self.create_paid_order(listener_user, [track_variant])

        response = self.listener_client.get(self.purchased_music_url)
        results = get_results(response)

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in results] == [track.album.id]
        assert results[0]['is_fully_available'] is False

    def test_purchased_music_returns_partial_album(
        self,
        listener_user,
    ):
        """Частично доступный релиз попадает в список с флагом partial."""
        owner = self.variant_factory('album').product.album.owner
        album = Album.objects.create(name='Partial Album', owner=owner)

        bought_track_variant = self.variant_factory(
            'track',
            name='Bought Track',
            album=album,
        )

        Track.objects.create(
            name='Not Bought Track',
            owner=album.owner,
            album=album,
        )

        self.create_paid_order(listener_user, [bought_track_variant])

        response = self.listener_client.get(self.purchased_music_url)
        results = get_results(response)

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in results] == [album.id]
        assert results[0]['is_fully_available'] is False

    def test_purchased_music_returns_full_release_when_all_tracks_bought(
        self,
        listener_user,
    ):
        """Если куплены все треки релиза отдельно, релиз доступен полностью."""
        first_track_variant = self.variant_factory(
            'track',
            name='First Track',
        )
        album = first_track_variant.product.track.album

        second_track_variant = self.variant_factory(
            'track',
            name='Second Track',
            album=album,
        )

        self.create_paid_order(
            listener_user,
            [first_track_variant, second_track_variant],
        )

        response = self.listener_client.get(self.purchased_music_url)
        results = get_results(response)

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in results] == [album.id]
        assert results[0]['is_fully_available'] is True

    def test_purchased_music_does_not_return_other_user_purchase(
        self,
        user_factory,
    ):
        """Покупки другого пользователя не попадают в библиотеку."""
        other_user = user_factory()
        track_variant = self.variant_factory('track', name='Other User Track')

        self.create_paid_order(other_user, [track_variant])

        response = self.listener_client.get(self.purchased_music_url)
        results = get_results(response)

        assert response.status_code == status.HTTP_200_OK
        assert results == []


class TestPurchasedMusicDownloadDetailAPI:
    """Тесты detail-ручки скачивания релиза."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        listener_client,
        purchased_music_download_detail_url,
        variant_factory,
    ) -> None:
        self.listener_client = listener_client
        self.download_detail_url = purchased_music_download_detail_url
        self.variant_factory = variant_factory

    def create_paid_order(
        self,
        listener_user,
        variants,
        order_status=Order.Status.PAID,
    ):
        """Создаёт оплаченный заказ с указанными вариантами."""
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

    @patch(
        'store.views.purchased_music.AlbumArchiveScheduler.schedule',
    )
    def test_full_release_returns_archive_and_all_tracks(
        self,
        schedule_mock,
        listener_user,
    ):
        """Полный доступ возвращает ZIP и все треки релиза."""
        album_variant = self.variant_factory(
            'album',
            name='Full Album',
        )
        album = album_variant.product.album

        first_track = Track.objects.create(
            name='First Track',
            owner=album.owner,
            album=album,
            position=1,
        )
        second_track = Track.objects.create(
            name='Second Track',
            owner=album.owner,
            album=album,
            position=2,
        )

        self.create_paid_order(listener_user, [album_variant])

        AlbumArchive.objects.create(
            album=album,
            status=AlbumArchive.Status.READY,
        )

        response = self.listener_client.get(
            self.download_detail_url(album),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['album_id'] == album.id
        assert response.data['access'] == 'full'

        assert response.data['items'] == [
            {
                'type': 'archive',
                'id': album.id,
                'title': 'Скачать альбом в .ZIP',
                'status': 'ready',
                'download_action_url': None,
            },
            {
                'type': 'track',
                'id': first_track.id,
                'title': '01. First Track',
                'status': 'ready',
                'download_action_url': None,
            },
            {
                'type': 'track',
                'id': second_track.id,
                'title': '02. Second Track',
                'status': 'ready',
                'download_action_url': None,
            },
        ]
        schedule_mock.assert_called_once_with(album)

    @patch(
        'store.views.purchased_music.AlbumArchiveScheduler.schedule',
    )
    def test_partial_release_returns_only_available_tracks(
        self,
        schedule_mock,
        listener_user,
    ):
        """Частичный доступ не возвращает archive item."""
        bought_track_variant = self.variant_factory(
            'track',
            name='Bought Track',
        )
        bought_track = bought_track_variant.product.track
        bought_track.position = 1
        bought_track.save(update_fields=('position',))

        album = bought_track.album

        Track.objects.create(
            name='Not Bought Track',
            owner=album.owner,
            album=album,
            position=2,
        )

        self.create_paid_order(
            listener_user,
            [bought_track_variant],
        )

        response = self.listener_client.get(
            self.download_detail_url(album),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'album_id': album.id,
            'access': 'partial',
            'items': [
                {
                    'type': 'track',
                    'id': bought_track.id,
                    'title': '01. Bought Track',
                    'status': 'ready',
                    'download_action_url': None,
                },
            ],
        }
        schedule_mock.assert_not_called()

    def test_other_user_cannot_get_download_detail(
        self,
        listener_user,
        user_factory,
    ):
        """Чужой доступный релиз не раскрывается."""
        other_user = user_factory()
        track_variant = self.variant_factory(
            'track',
            name='Other User Track',
        )
        album = track_variant.product.track.album

        self.create_paid_order(other_user, [track_variant])

        response = self.listener_client.get(
            self.download_detail_url(album),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
