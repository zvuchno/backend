"""Тесты API треков."""

from decimal import Decimal
from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.urls import reverse

from store.constants import CHAR_PRESET_DIGITAL
from store.models import Recording, ReleaseTrack
from store.services import ProductService
from store.tests.factories import (
    AlbumFactory,
    ReleaseTrackFactory,
    make_audio_file,
)


@pytest.mark.django_db
class TestTrackCreate:
    """Тесты создания трека через API."""

    @patch('store.serializers.track.TrackGeneratedAudioScheduler.schedule')
    def test_create_track(
        self,
        mocked_schedule,
        artist_client,
        artist_user,
        track_list_url,
    ):
        """Создание трека создаёт запись, размещение и цифровой товар."""
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
                'price': '100.00',
                'allow_overpay': False,
                'description': 'Описание трека.',
                'isrc': 'RUA1B2600001',
            },
            format='multipart',
        )

        assert response.status_code == HTTPStatus.CREATED

        recording = Recording.objects.get(name='Новый трек')
        track = ReleaseTrack.objects.get(recording=recording)

        assert recording.created_by == artist_user
        assert recording.owner == album.artist
        assert recording.description == 'Описание трека.'
        assert recording.isrc == 'RUA1B2600001'
        assert recording.audio_file

        assert track.release == album
        assert track.recording == recording

        assert track.product.price == Decimal('100.00')
        assert track.product.allow_overpay is False
        assert track.product.variants.filter(
            property_value=CHAR_PRESET_DIGITAL,
            is_active=True,
        ).exists()

        mocked_schedule.assert_called_once_with(recording)

        assert response.data['id'] == track.id
        assert response.data['album'] == album.id
        assert response.data['name'] == 'Новый трек'
        assert response.data['isrc'] == 'RUA1B2600001'


@pytest.mark.django_db
class TestTrackUpdate:
    """Тесты обновления трека через API."""

    @pytest.fixture
    def track(self, artist_user):
        """Создаёт трек с коммерческими настройками."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            payout_recipient=artist_user,
            created_by=artist_user,
        )
        track = ReleaseTrackFactory(
            release=album,
            recording__name='Старое название',
            recording__description='Старое описание.',
            recording__isrc='RUA1B2600001',
            recording__file_hash='existing-hash',
        )

        ProductService.ensure_commerce(
            track,
            {
                'price': Decimal('100.00'),
                'allow_overpay': True,
            },
        )

        return track

    @patch('store.serializers.track.TrackGeneratedAudioScheduler.schedule')
    def test_update_track_metadata_and_commerce(
        self,
        mocked_schedule,
        artist_client,
        track,
    ):
        """PATCH обновляет запись и торговые настройки трека."""
        url = reverse(
            'api:store:tracks-detail',
            args=(track.pk,),
        )

        response = artist_client.patch(
            url,
            {
                'name': 'Новое название',
                'description': 'Новое описание.',
                'isrc': '',
                'price': '250.00',
                'allow_overpay': False,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        track.refresh_from_db()
        track.recording.refresh_from_db()
        track.product.refresh_from_db()

        assert track.recording.name == 'Новое название'
        assert track.recording.description == 'Новое описание.'
        assert track.recording.isrc is None
        assert track.recording.file_hash == 'existing-hash'

        assert track.product.price == Decimal('250.00')
        assert track.product.allow_overpay is False

        mocked_schedule.assert_not_called()

        assert response.data['name'] == 'Новое название'
        assert response.data['description'] == 'Новое описание.'
        assert response.data['isrc'] is None

    @patch('store.serializers.track.TrackGeneratedAudioScheduler.schedule')
    def test_update_audio_file_schedules_generation(
        self,
        mocked_schedule,
        artist_client,
        track,
    ):
        """Замена оригинала запускает повторную подготовку аудио."""
        url = reverse(
            'api:store:tracks-detail',
            args=(track.pk,),
        )
        old_audio_name = track.recording.audio_file.name

        response = artist_client.patch(
            url,
            {
                'audio_file': make_audio_file(
                    name='replacement.mp3',
                ),
            },
            format='multipart',
        )

        assert response.status_code == HTTPStatus.OK

        track.recording.refresh_from_db()

        assert track.recording.audio_file.name != old_audio_name
        assert track.recording.file_hash == ''
        mocked_schedule.assert_called_once_with(track.recording)

    def test_cannot_change_track_album(
        self,
        artist_client,
        artist_user,
        track,
    ):
        """Нельзя перенести существующий трек в другой релиз через PATCH."""
        another_album = AlbumFactory(
            artist=artist_user.artist_profile,
            payout_recipient=artist_user,
            created_by=artist_user,
        )
        url = reverse(
            'api:store:tracks-detail',
            args=(track.pk,),
        )

        original_release_id = track.release_id

        response = artist_client.patch(
            url,
            {'album': another_album.pk},
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'album' in response.data

        track.refresh_from_db()

        assert track.release_id != another_album.pk
        assert track.release_id == original_release_id
