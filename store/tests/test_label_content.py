"""Тесты создания контента от имени профилей лейбла."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from store.models import Album, Merch, Track
from store.tests.factories import (
    AlbumFactory,
    GenreFactory,
    MerchKindFactory,
    make_audio_file,
)


@pytest.mark.django_db
class TestLabelAlbumCreate:
    """Тесты создания альбомов лейблом."""

    @pytest.fixture
    def album_payload(self):
        genre = GenreFactory()

        return {
            'name': 'Альбом лейбла',
            'is_single': False,
            'release_date': '2026-01-01',
            'genre': genre.id,
            'price': '500.00',
            'description': 'Описание альбома.',
            'allow_overpay': False,
            'visibility': 'public',
            'is_published': False,
        }

    def test_label_must_explicitly_select_profile(
        self,
        label_client,
        album_list_url,
        album_payload,
    ):
        response = label_client.post(
            album_list_url,
            album_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'artist' in response.data

    def test_label_creates_album_for_self(
        self,
        label_client,
        ready_label_user,
        album_list_url,
        album_payload,
    ):
        album_payload['artist'] = ready_label_user.artist_profile.id

        response = label_client.post(
            album_list_url,
            album_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        album = Album.objects.get(name='Альбом лейбла')

        assert album.artist == ready_label_user.artist_profile
        assert album.created_by == ready_label_user
        assert album.payout_recipient == ready_label_user

    def test_label_creates_album_for_managed_artist(
        self,
        label_client,
        ready_label_user,
        label_created_artist,
        album_list_url,
        album_payload,
    ):
        album_payload['artist'] = label_created_artist.id

        response = label_client.post(
            album_list_url,
            album_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        album = Album.objects.get(name='Альбом лейбла')

        assert album.artist == label_created_artist
        assert album.created_by == ready_label_user
        assert album.payout_recipient == ready_label_user

    def test_label_cannot_create_album_for_foreign_artist(
        self,
        label_client,
        other_artist_user,
        album_list_url,
        album_payload,
    ):
        album_payload['artist'] = other_artist_user.artist_profile.id

        response = label_client.post(
            album_list_url,
            album_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert not Album.objects.filter(name='Альбом лейбла').exists()

    def test_artist_creates_album_without_artist_field(
        self,
        artist_client,
        ready_artist_user,
        album_list_url,
        album_payload,
    ):
        response = artist_client.post(
            album_list_url,
            album_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        album = Album.objects.get(name='Альбом лейбла')

        assert album.artist == ready_artist_user.artist_profile
        assert album.created_by == ready_artist_user
        assert album.payout_recipient == ready_artist_user


@pytest.mark.django_db
class TestLabelMerchCreate:
    """Тесты создания мерча лейблом."""

    @pytest.fixture
    def merch_payload(self):
        kind = MerchKindFactory()

        return {
            'name': 'Мерч лейбла',
            'kind': kind.id,
            'price': '1000.00',
            'description': 'Описание мерча.',
            'allow_overpay': False,
            'visibility': 'public',
            'is_published': True,
            'stock': 10,
        }

    def test_label_must_explicitly_select_profile(
        self,
        label_client,
        merch_list_url,
        merch_payload,
    ):
        response = label_client.post(
            merch_list_url,
            merch_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'artist' in response.data

    def test_label_creates_merch_for_self(
        self,
        label_client,
        ready_physical_label_user,
        merch_list_url,
        merch_payload,
    ):
        merch_payload['artist'] = ready_physical_label_user.artist_profile.id

        response = label_client.post(
            merch_list_url,
            merch_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        merch = Merch.objects.get(name='Мерч лейбла')

        assert merch.artist == ready_physical_label_user.artist_profile
        assert merch.created_by == ready_physical_label_user
        assert merch.payout_recipient == ready_physical_label_user

    def test_label_creates_merch_for_managed_artist(
        self,
        label_client,
        ready_physical_label_user,
        label_created_artist,
        merch_list_url,
        merch_payload,
    ):
        merch_payload['artist'] = label_created_artist.id

        response = label_client.post(
            merch_list_url,
            merch_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        merch = Merch.objects.get(name='Мерч лейбла')
        assert merch.artist == label_created_artist
        assert merch.created_by == ready_physical_label_user
        assert merch.payout_recipient == ready_physical_label_user

    def test_label_cannot_create_merch_for_foreign_artist(
        self,
        label_client,
        other_artist_user,
        merch_list_url,
        merch_payload,
    ):
        merch_payload['artist'] = other_artist_user.artist_profile.id

        response = label_client.post(
            merch_list_url,
            merch_payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert not Merch.objects.filter(name='Мерч лейбла').exists()


@pytest.mark.django_db
class TestLabelTrackCreate:
    """Тесты создания треков лейблом."""

    @patch(
        'store.serializers.track.TrackGeneratedAudioScheduler.schedule',
    )
    def test_label_creates_track_for_managed_artist(
        self,
        mocked_schedule,
        label_client,
        label_user,
        label_created_artist,
        track_list_url,
    ):
        album = AlbumFactory(
            artist=label_created_artist,
            created_by=label_user,
            payout_recipient=label_user,
        )
        response = label_client.post(
            track_list_url,
            {
                'album': album.id,
                'name': 'Трек артиста лейбла',
                'audio_file': make_audio_file(),
                'position': 1,
                'price': '100.00',
                'allow_overpay': False,
            },
            format='multipart',
        )

        assert response.status_code == HTTPStatus.CREATED

        track = Track.objects.get(
            name='Трек артиста лейбла',
        )

        assert track.album == album
        assert track.artist == label_created_artist
        assert track.created_by == label_user
        assert track.payout_recipient == label_user

        mocked_schedule.assert_called_once_with(track)

    @patch(
        'store.serializers.track.TrackGeneratedAudioScheduler.schedule',
    )
    def test_label_cannot_create_track_in_foreign_album(
        self,
        mocked_schedule,
        label_client,
        other_artist_user,
        track_list_url,
    ):
        foreign_album = AlbumFactory(
            artist=other_artist_user.artist_profile,
            created_by=other_artist_user,
            payout_recipient=other_artist_user,
        )

        response = label_client.post(
            track_list_url,
            {
                'album': foreign_album.id,
                'name': 'Чужой трек',
                'audio_file': make_audio_file(),
                'position': 1,
                'price': '100.00',
                'allow_overpay': False,
            },
            format='multipart',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'album' in response.data
        assert not Track.objects.filter(name='Чужой трек').exists()

        mocked_schedule.assert_not_called()
