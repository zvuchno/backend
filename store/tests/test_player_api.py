"""Тесты API плеера."""

from decimal import Decimal

import pytest
from rest_framework import status

from store.constants import PREVIEW_DURATION
from store.models import Favorite, Order, OrderItem, Track, TrackGeneratedAudio

pytestmark = pytest.mark.django_db


def create_paid_order(user, variant) -> Order:
    """Создаёт оплаченный заказ с указанным вариантом."""
    order = Order.objects.create(
        user=user,
        status=Order.Status.PAID,
        total=variant.product.price,
    )

    OrderItem.objects.create(
        order=order,
        product_variant=variant,
        price_at_purchase=variant.product.price,
        unit_price=variant.product.price,
        quantity=1,
        product_info={'name': str(variant.product)},
    )

    return order


class TestPlayerAlbumAPI:
    """Тесты получения очереди воспроизведения альбома."""

    @staticmethod
    def create_ready_preview(track) -> TrackGeneratedAudio:
        """Создаёт готовое preview трека."""
        generated = TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
            preview_duration=PREVIEW_DURATION,
        )
        generated.preview_file.name = 'test/previews/preview.mp3'
        generated.save(update_fields=('preview_file',))

        return generated

    @staticmethod
    def create_ready_stream(track) -> TrackGeneratedAudio:
        """Создаёт готовую полную версию трека."""
        generated = TrackGeneratedAudio.objects.create(
            track=track,
            stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
        )
        generated.stream_file.name = 'test/streams/stream.mp3'
        generated.save(update_fields=('stream_file',))

        return generated

    def test_returns_album_with_tracks_in_position_order(
        self,
        api_client,
        player_album_url,
        player_track_play_url,
        variant_factory,
    ):
        """Возвращает альбом и треки в порядке их позиции."""
        first_variant = variant_factory(
            'track',
            name='Первый трек',
            price=Decimal('300.00'),
        )
        first_track = first_variant.product.track
        album = first_track.album

        second_variant = variant_factory(
            'track',
            album=album,
            name='Второй трек',
            price=Decimal('330.00'),
        )
        second_track = second_variant.product.track

        first_track.position = 1
        first_track.save(update_fields=('position',))

        second_track.position = 2
        second_track.save(update_fields=('position',))

        self.create_ready_preview(first_track)

        TrackGeneratedAudio.objects.create(
            track=second_track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.BUILDING,
        )

        response = api_client.get(
            player_album_url(album.id),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == album.id
        assert response.data['name'] == album.name
        assert response.data['artist_name'] == (album.artist.name)
        assert response.data['cover_image'] == (
            album.cover_image.url if album.cover_image else None
        )

        tracks = response.data['tracks']

        assert [track['id'] for track in tracks] == [
            first_track.id,
            second_track.id,
        ]

        assert tracks[0]['name'] == first_track.name
        assert tracks[0]['duration'] == first_track.duration
        assert tracks[0]['purchase']['price'] == str(
            first_variant.product.price,
        )
        assert tracks[0]['is_favorite'] is False
        assert tracks[0]['playback'] == {
            'status': TrackGeneratedAudio.ProcessingStatus.READY,
            'kind': 'preview',
            'duration': PREVIEW_DURATION,
            'url': player_track_play_url(first_track.id),
        }

        assert tracks[1]['name'] == second_track.name
        assert tracks[1]['playback'] == {
            'status': TrackGeneratedAudio.ProcessingStatus.BUILDING,
            'kind': None,
            'duration': None,
            'url': None,
        }

    def test_does_not_return_inactive_tracks(
        self,
        api_client,
        player_album_url,
        variant_factory,
    ):
        """Неактивные треки не попадают в очередь альбома."""
        active_variant = variant_factory(
            'track',
            name='Активный трек',
        )
        active_track = active_variant.product.track
        album = active_track.album

        inactive_variant = variant_factory(
            'track',
            album=album,
            name='Неактивный трек',
        )
        inactive_track = inactive_variant.product.track

        active_track.position = 1
        active_track.save(update_fields=('position',))

        inactive_track.position = 2
        inactive_track.is_active = False
        inactive_track.save(
            update_fields=(
                'position',
                'is_active',
            ),
        )

        response = api_client.get(
            player_album_url(album.id),
        )

        assert response.status_code == status.HTTP_200_OK
        assert [track['id'] for track in response.data['tracks']] == [
            active_track.id,
        ]

    def test_returns_favorite_state_for_authenticated_user(
        self,
        api_client,
        listener_user,
        player_album_url,
        variant_factory,
    ):
        """Возвращает статус избранного для текущего пользователя."""
        variant = variant_factory(
            'track',
            name='Избранный трек',
        )
        track = variant.product.track

        Favorite.objects.create(
            user=listener_user,
            product_variant=variant,
        )

        api_client.force_authenticate(user=listener_user)

        response = api_client.get(
            player_album_url(track.album.id),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['tracks'][0]['id'] == track.id
        assert response.data['tracks'][0]['is_favorite'] is True

    def test_returns_404_for_unpublished_album(
        self,
        api_client,
        player_album_url,
        variant_factory,
    ):
        """Неопубликованный альбом недоступен анонимному пользователю."""
        variant = variant_factory('track')
        album = variant.product.track.album

        album.is_published = False
        album.save(update_fields=('is_published',))

        response = api_client.get(
            player_album_url(album.id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_empty_purchase_for_track_with_zero_price(
        self,
        api_client,
        player_album_url,
        variant_factory,
    ):
        """Не отдаёт покупку для трека, который не продаётся."""
        variant = variant_factory(
            'track',
            price=Decimal('300.00'),
            allow_overpay=True,
        )
        track = variant.product.track

        variant.product.price = Decimal('0.00')
        variant.product.save(update_fields=('price',))

        response = api_client.get(
            player_album_url(track.album.id),
        )

        assert response.status_code == status.HTTP_200_OK

        player_track = response.data['tracks'][0]

        assert player_track['purchase'] is None

    def test_returns_full_playback_for_purchased_track(
        self,
        api_client,
        listener_user,
        player_album_url,
        player_track_play_url,
        variant_factory,
    ):
        """Купленный отдельно трек доступен в полной версии."""
        variant = variant_factory(
            'track',
            name='Купленный трек',
        )
        track = variant.product.track

        self.create_ready_stream(track)
        create_paid_order(listener_user, variant)

        api_client.force_authenticate(user=listener_user)

        response = api_client.get(
            player_album_url(track.album.id),
        )

        assert response.status_code == status.HTTP_200_OK

        player_track = response.data['tracks'][0]

        assert player_track['playback'] == {
            'status': TrackGeneratedAudio.ProcessingStatus.READY,
            'kind': 'full',
            'duration': track.duration,
            'url': player_track_play_url(track.id),
        }

    def test_returns_full_playback_for_track_from_purchased_album(
        self,
        api_client,
        listener_user,
        player_album_url,
        player_track_play_url,
        variant_factory,
    ):
        """Трек купленного альбома доступен в полной версии."""
        album_variant = variant_factory(
            'album',
            name='Купленный альбом',
        )
        album = album_variant.product.album

        track_variant = variant_factory(
            'track',
            album=album,
            name='Трек альбома',
        )
        track = track_variant.product.track

        self.create_ready_stream(track)
        create_paid_order(listener_user, album_variant)

        api_client.force_authenticate(user=listener_user)

        response = api_client.get(
            player_album_url(album.id),
        )

        assert response.status_code == status.HTTP_200_OK

        player_track = response.data['tracks'][0]

        assert player_track['id'] == track.id
        assert player_track['playback'] == {
            'status': TrackGeneratedAudio.ProcessingStatus.READY,
            'kind': 'full',
            'duration': track.duration,
            'url': player_track_play_url(track.id),
        }

    def test_returns_preview_for_purchased_track_while_stream_building(
        self,
        api_client,
        listener_user,
        player_album_url,
        player_track_play_url,
        variant_factory,
    ):
        """Для купленного трека возвращается preview, пока stream готовится."""
        variant = variant_factory(
            'track',
            name='Купленный трек',
        )
        track = variant.product.track

        generated = TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
            preview_duration=PREVIEW_DURATION,
            stream_status=TrackGeneratedAudio.ProcessingStatus.BUILDING,
        )
        generated.preview_file.name = 'test/previews/preview.mp3'
        generated.save(update_fields=('preview_file',))

        create_paid_order(listener_user, variant)

        api_client.force_authenticate(user=listener_user)

        response = api_client.get(
            player_album_url(track.album.id),
        )

        assert response.status_code == status.HTTP_200_OK

        playback = response.data['tracks'][0]['playback']

        assert playback == {
            'status': TrackGeneratedAudio.ProcessingStatus.READY,
            'kind': 'preview',
            'duration': PREVIEW_DURATION,
            'url': player_track_play_url(track.id),
        }


class TestPlayerTrackPlayAPI:
    """Тесты запуска воспроизведения трека."""

    @staticmethod
    def create_track(variant_factory) -> Track:
        """Создаёт публичный трек с товаром."""
        variant = variant_factory('track')
        return variant.product.track

    @staticmethod
    def create_ready_preview(track) -> TrackGeneratedAudio:
        """Создаёт запись о готовом preview трека."""
        generated = TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
            preview_duration=PREVIEW_DURATION,
        )
        generated.preview_file.name = 'test/previews/preview.mp3'
        generated.save(update_fields=('preview_file',))

        return generated

    @staticmethod
    def create_ready_stream(track) -> TrackGeneratedAudio:
        """Создаёт запись о готовой полной версии трека."""
        generated = TrackGeneratedAudio.objects.create(
            track=track,
            stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
        )
        generated.stream_file.name = 'test/streams/stream.mp3'
        generated.save(update_fields=('stream_file',))

        return generated

    def test_ready_preview_redirects_to_audio_file(
        self,
        api_client,
        monkeypatch,
        player_track_play_url,
        variant_factory,
    ):
        """Готовое preview перенаправляет на аудиофайл."""
        track = self.create_track(variant_factory)
        generated = self.create_ready_preview(track)

        storage = generated.preview_file.storage

        monkeypatch.setattr(
            storage,
            'exists',
            lambda name: True,
        )

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response['Location'] == generated.preview_file.url

    def test_missing_generated_audio_returns_pending_status(
        self,
        api_client,
        player_track_play_url,
        variant_factory,
    ):
        """Трек без производного аудио считается ожидающим обработки."""
        track = self.create_track(variant_factory)

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data == {
            'detail': 'Превью трека ещё готовится.',
            'status': TrackGeneratedAudio.ProcessingStatus.PENDING,
        }

    @pytest.mark.parametrize(
        'preview_status',
        (
            TrackGeneratedAudio.ProcessingStatus.PENDING,
            TrackGeneratedAudio.ProcessingStatus.BUILDING,
        ),
        ids=(
            'pending',
            'building',
        ),
    )
    def test_not_ready_preview_returns_409(
        self,
        api_client,
        player_track_play_url,
        variant_factory,
        preview_status,
    ):
        """Неготовое preview возвращает 409 с текущим статусом."""
        track = self.create_track(variant_factory)

        TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=preview_status,
        )

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data == {
            'detail': 'Превью трека ещё готовится.',
            'status': preview_status,
        }

    def test_failed_preview_returns_409(
        self,
        api_client,
        player_track_play_url,
        variant_factory,
    ):
        """Ошибка подготовки preview возвращает 409."""
        track = self.create_track(variant_factory)

        TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
        )

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data == {
            'detail': 'Не удалось подготовить превью трека.',
            'status': TrackGeneratedAudio.ProcessingStatus.FAILED,
        }

    def test_ready_preview_without_file_returns_404(
        self,
        api_client,
        player_track_play_url,
        variant_factory,
    ):
        """Статус ready без готового файла не выдаёт redirect."""
        track = self.create_track(variant_factory)

        TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
            preview_duration=PREVIEW_DURATION,
        )

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {
            'detail': 'Превью трека временно недоступно.',
            'code': 'preview_file_missing',
        }

    def test_ready_preview_without_duration_returns_404(
        self,
        api_client,
        player_track_play_url,
        variant_factory,
    ):
        """Preview без длительности не выдаётся как готовое."""
        track = self.create_track(variant_factory)

        generated = TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
        )
        generated.preview_file.name = 'test/previews/preview.mp3'
        generated.save(update_fields=('preview_file',))

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {
            'detail': 'Превью трека временно недоступно.',
            'code': 'preview_duration_missing',
        }

    def test_returns_404_for_inaccessible_track(
        self,
        api_client,
        player_track_play_url,
        variant_factory,
    ):
        """Трек неопубликованного альбома нельзя запустить."""
        track = self.create_track(variant_factory)

        track.album.is_published = False
        track.album.save(update_fields=('is_published',))

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_purchased_track_redirects_to_stream_file(
        self,
        api_client,
        listener_user,
        monkeypatch,
        player_track_play_url,
        variant_factory,
    ):
        """Купленный трек перенаправляет на полную версию."""
        variant = variant_factory('track')
        track = variant.product.track
        generated = self.create_ready_stream(track)

        create_paid_order(listener_user, variant)

        storage = generated.stream_file.storage

        monkeypatch.setattr(
            storage,
            'exists',
            lambda name: True,
        )

        api_client.force_authenticate(user=listener_user)

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response['Location'] == generated.stream_file.url

    def test_purchased_track_falls_back_to_preview_while_stream_building(
        self,
        api_client,
        listener_user,
        monkeypatch,
        player_track_play_url,
        variant_factory,
    ):
        """Для купленного трека используется preview, пока stream готовится."""
        variant = variant_factory('track')
        track = variant.product.track

        generated = TrackGeneratedAudio.objects.create(
            track=track,
            preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
            preview_duration=PREVIEW_DURATION,
            stream_status=TrackGeneratedAudio.ProcessingStatus.BUILDING,
        )
        generated.preview_file.name = 'test/previews/preview.mp3'
        generated.save(update_fields=('preview_file',))

        create_paid_order(listener_user, variant)

        monkeypatch.setattr(
            generated.preview_file.storage,
            'exists',
            lambda name: True,
        )

        api_client.force_authenticate(user=listener_user)

        response = api_client.get(
            player_track_play_url(track.id),
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response['Location'] == generated.preview_file.url
