from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status

from store.models import AlbumArchive, Order, OrderItem, Track
from store.services import DownloadLink


class TestPurchasedMusicTrackDownloadLinkAPI:
    """Тесты ручки выдачи временной ссылки на отдельный трек."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        listener_client,
        purchased_music_track_download_link_url,
        variant_factory,
    ) -> None:
        self.listener_client = listener_client
        self.track_download_link_url = purchased_music_track_download_link_url
        self.variant_factory = variant_factory

    @staticmethod
    def create_paid_order(
        listener_user,
        variants,
        order_status=Order.Status.PAID,
    ) -> Order:
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

    def test_available_track_returns_download_link(self, listener_user):
        """Купленный трек возвращает свежую ссылку на скачивание."""
        track_variant = self.variant_factory(
            'track',
            name='Available Track',
        )
        track = track_variant.product.track

        track.audio_file = 'tracks/available-track.flac'
        track.save(update_fields=('audio_file',))

        self.create_paid_order(listener_user, [track_variant])

        link = DownloadLink(
            url='https://storage.example/signed-track-url',
            filename='Artist — Album (2026) — 01 — Track.flac',
            expires_in=600,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        with patch(
            'store.views.purchased_music.DownloadLinkService.get_link',
            return_value=link,
        ) as get_link_mock:
            response = self.listener_client.post(
                self.track_download_link_url(track),
            )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response.data['url'] == 'https://storage.example/signed-track-url'
        )
        assert response.data['filename'] == link.filename
        assert response.data['expires_in'] == 600
        assert response.data['expires_at'] is not None

        get_link_mock.assert_called_once()
        assert get_link_mock.call_args.kwargs['field_file'] == track.audio_file

    def test_other_user_cannot_get_track_download_link(
        self,
        listener_user,
        user_factory,
    ):
        """Пользователь не получает ссылку на чужой купленный трек."""
        other_user = user_factory()

        track_variant = self.variant_factory(
            'track',
            name='Other User Track',
        )
        track = track_variant.product.track

        track.audio_file = 'tracks/other-user-track.flac'
        track.save(update_fields=('audio_file',))

        self.create_paid_order(other_user, [track_variant])

        response = self.listener_client.post(
            self.track_download_link_url(track),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_track_without_audio_file_returns_404(self, listener_user):
        """Трек без файла не выдаёт ссылку."""
        track_variant = self.variant_factory(
            'track',
            name='Track Without File',
        )
        track = track_variant.product.track

        track.audio_file = ''
        track.save(update_fields=('audio_file',))

        self.create_paid_order(listener_user, [track_variant])

        response = self.listener_client.post(
            self.track_download_link_url(track),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {
            'detail': 'Файл трека временно недоступен.',
        }

    def test_missing_track_file_in_storage_returns_404(self, listener_user):
        """Пропавший из storage файл трека не выдаёт ссылку."""
        track_variant = self.variant_factory(
            'track',
            name='Missing Track File',
        )
        track = track_variant.product.track

        track.audio_file = 'tracks/missing-track.flac'
        track.save(update_fields=('audio_file',))

        self.create_paid_order(listener_user, [track_variant])

        with patch(
            'store.views.purchased_music.DownloadLinkService.get_link',
            side_effect=FileNotFoundError,
        ):
            response = self.listener_client.post(
                self.track_download_link_url(track),
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {
            'detail': 'Файл трека временно недоступен.',
        }


class TestPurchasedMusicArchiveDownloadLinkAPI:
    """Тесты ручки выдачи временной ссылки на ZIP-архив."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        listener_client,
        purchased_music_archive_download_link_url,
        variant_factory,
    ) -> None:
        self.listener_client = listener_client
        self.archive_download_link_url = (
            purchased_music_archive_download_link_url
        )
        self.variant_factory = variant_factory

    @staticmethod
    def create_paid_order(
        listener_user,
        variants,
        order_status=Order.Status.PAID,
    ) -> Order:
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

    def create_full_access_album(self, listener_user):
        """Создаёт купленный альбом с треками и возвращает его."""
        album_variant = self.variant_factory(
            'album',
            name='Purchased Album',
        )
        album = album_variant.product.album

        Track.objects.create(
            name='First Track',
            owner=album.owner,
            album=album,
            position=1,
        )
        Track.objects.create(
            name='Second Track',
            owner=album.owner,
            album=album,
            position=2,
        )

        self.create_paid_order(listener_user, [album_variant])

        return album

    def test_ready_archive_returns_download_link(self, listener_user):
        """Готовый архив полного доступного релиза возвращает ссылку."""
        album = self.create_full_access_album(listener_user)

        archive = AlbumArchive.objects.create(
            album=album,
            status=AlbumArchive.Status.READY,
        )
        archive.file = 'archives/purchased-album.zip'
        archive.save(update_fields=('file',))

        link = DownloadLink(
            url='https://storage.example/signed-archive-url',
            filename='Artist — Purchased Album (2026).zip',
            expires_in=600,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        with (
            patch(
                'store.views.purchased_music.AlbumArchiveScheduler.schedule',
            ) as schedule_mock,
            patch(
                'store.views.purchased_music.DownloadLinkService.get_link',
                return_value=link,
            ) as get_link_mock,
        ):
            response = self.listener_client.post(
                self.archive_download_link_url(album),
            )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response.data['url']
            == 'https://storage.example/signed-archive-url'
        )
        assert response.data['filename'] == link.filename
        assert response.data['expires_in'] == 600
        assert response.data['expires_at'] is not None

        schedule_mock.assert_called_once_with(album)
        get_link_mock.assert_called_once()
        assert get_link_mock.call_args.kwargs['field_file'] == archive.file

    def test_partial_access_cannot_get_archive_download_link(
        self,
        listener_user,
    ):
        """Частично доступный альбом не выдаёт ZIP-архив."""
        track_variant = self.variant_factory(
            'track',
            name='Bought Track',
        )
        bought_track = track_variant.product.track
        album = bought_track.album

        Track.objects.create(
            name='Not Bought Track',
            owner=album.owner,
            album=album,
            position=2,
        )

        self.create_paid_order(listener_user, [track_variant])

        response = self.listener_client.post(
            self.archive_download_link_url(album),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        'archive_status',
        [
            AlbumArchive.Status.PENDING,
            AlbumArchive.Status.BUILDING,
            AlbumArchive.Status.FAILED,
        ],
    )
    def test_not_ready_archive_returns_409(
        self,
        listener_user,
        archive_status,
    ):
        """Неготовый архив возвращает 409 с текущим статусом."""
        album = self.create_full_access_album(listener_user)

        AlbumArchive.objects.create(
            album=album,
            status=archive_status,
        )

        with patch(
            'store.views.purchased_music.AlbumArchiveScheduler.schedule',
        ) as schedule_mock:
            response = self.listener_client.post(
                self.archive_download_link_url(album),
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data == {
            'detail': 'Архив ещё не готов.',
            'status': archive_status,
        }

        schedule_mock.assert_called_once_with(album)

    def test_ready_archive_without_file_returns_404(self, listener_user):
        """Готовый архив без файла не выдаёт ссылку."""
        album = self.create_full_access_album(listener_user)

        AlbumArchive.objects.create(
            album=album,
            status=AlbumArchive.Status.READY,
            file='',
        )

        with patch(
            'store.views.purchased_music.AlbumArchiveScheduler.schedule',
        ):
            response = self.listener_client.post(
                self.archive_download_link_url(album),
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {
            'detail': 'Файл архива временно недоступен.',
        }

    def test_missing_archive_file_in_storage_returns_404(
        self,
        listener_user,
    ):
        """Удалённый из storage ZIP не выдаёт ссылку."""
        album = self.create_full_access_album(listener_user)

        archive = AlbumArchive.objects.create(
            album=album,
            status=AlbumArchive.Status.READY,
        )
        archive.file = 'archives/missing-album.zip'
        archive.save(update_fields=('file',))

        with (
            patch(
                'store.views.purchased_music.AlbumArchiveScheduler.schedule',
            ),
            patch(
                'store.views.purchased_music.DownloadLinkService.get_link',
                side_effect=FileNotFoundError,
            ),
        ):
            response = self.listener_client.post(
                self.archive_download_link_url(album),
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {
            'detail': 'Файл архива временно недоступен.',
        }
