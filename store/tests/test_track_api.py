"""Тесты API треков."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from store.models import Track
from store.tests.factories import AlbumFactory, make_audio_file


@pytest.mark.django_db
class TestTrackCreate:
    """Тесты создания трека через API."""

    @patch('store.serializers.track.TrackGeneratedAudioScheduler.schedule')
    def test_create_track_sets_created_by(
        self,
        mocked_schedule,
        artist_client,
        artist_user,
        track_list_url,
    ):
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            payout_recipient=artist_user,
            created_by=artist_user,
        )

        response = artist_client.post(
            track_list_url,
            {
                'name': 'Новый трек',
                'album': album.id,
                'audio_file': make_audio_file(),
                'position': 1,
                'price': '100.00',
                'allow_overpay': False,
                'description': 'Описание трека.',
            },
            format='multipart',
        )

        assert response.status_code == HTTPStatus.CREATED

        track = Track.objects.get(name='Новый трек')

        assert track.created_by == artist_user
        assert track.album == album
        mocked_schedule.assert_called_once_with(track)
