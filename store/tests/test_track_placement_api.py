"""Тесты API добавления существующей записи в релиз."""

from decimal import Decimal

import pytest
from rest_framework import status

from store.models import Album, Recording, ReleaseTrack
from store.tests.factories import AlbumFactory, RecordingFactory


@pytest.fixture
def album(artist_user):
    """Неопубликованный релиз текущего артиста."""
    return AlbumFactory(
        artist=artist_user.artist_profile,
        created_by=artist_user,
        is_published=False,
    )


@pytest.fixture
def recording(artist_user):
    """Мастер-запись текущего артиста."""
    return RecordingFactory(
        owner=artist_user.artist_profile,
        created_by=artist_user,
    )


@pytest.mark.django_db
class TestTrackPlacementAPI:
    """POST /albums/{album_id}/tracks/."""

    def test_creates_placement(
        self,
        artist_client,
        album,
        recording,
        track_placement_url,
    ):
        """Создаёт размещение с отдельными коммерческими данными."""
        response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '150.00',
                'allow_overpay': True,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        track = ReleaseTrack.objects.get(
            release=album,
            recording=recording,
        )

        assert response.data['id'] == track.pk
        assert response.data['name'] == recording.name
        assert response.data['album'] == album.pk
        assert response.data['position'] == 1

        assert Decimal(response.data['price']) == Decimal('150.00')
        assert response.data['allow_overpay'] is True

        assert track.product.price == Decimal('150.00')
        assert track.product.allow_overpay is True

    def test_does_not_create_another_recording(
        self,
        artist_client,
        album,
        recording,
        track_placement_url,
    ):
        """API использует готовую мастер-запись."""
        initial_count = Recording.objects.count()

        response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '100.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Recording.objects.count() == initial_count

        track = ReleaseTrack.objects.get(pk=response.data['id'])
        assert track.recording_id == recording.pk

    def test_rejects_duplicate(
        self,
        artist_client,
        album,
        recording,
        track_placement_url,
    ):
        """Повторный POST не создаёт дубль и не меняет цену."""
        first_response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '100.00',
            },
            format='json',
        )

        assert first_response.status_code == status.HTTP_201_CREATED

        second_response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '500.00',
            },
            format='json',
        )

        assert second_response.status_code == status.HTTP_400_BAD_REQUEST

        tracks = ReleaseTrack.objects.filter(
            release=album,
            recording=recording,
        )

        assert tracks.count() == 1
        assert tracks.get().product.price == Decimal('100.00')

    def test_rejects_foreign_recording(
        self,
        artist_client,
        other_artist_user,
        album,
        track_placement_url,
    ):
        """Нельзя использовать запись неподконтрольного артиста."""
        foreign_recording = RecordingFactory(
            owner=other_artist_user.artist_profile,
            created_by=other_artist_user,
        )

        response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': foreign_recording.pk,
                'price': '100.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not album.tracks.exists()

    def test_rejects_foreign_release(
        self,
        artist_client,
        other_artist_user,
        recording,
        track_placement_url,
    ):
        """Нельзя добавлять даже свою запись в чужой релиз."""
        foreign_album = AlbumFactory(
            artist=other_artist_user.artist_profile,
            created_by=other_artist_user,
            is_published=False,
        )

        response = artist_client.post(
            track_placement_url(foreign_album),
            {
                'recording_id': recording.pk,
                'price': '100.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not foreign_album.tracks.exists()

    def test_label_can_place_recording_of_another_managed_artist(
        self,
        label_client,
        label_user,
        label_created_artist,
        signed_artist_user,
        track_placement_url,
    ):
        """Лейбл может связывать записи и релизы своих артистов."""
        album = AlbumFactory(
            artist=signed_artist_user.artist_profile,
            created_by=signed_artist_user,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=label_created_artist,
            created_by=label_user,
        )

        response = label_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '250.00',
                'allow_overpay': True,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        track = ReleaseTrack.objects.get(pk=response.data['id'])

        assert track.recording.owner_id == label_created_artist.pk
        assert track.release.artist_id == signed_artist_user.artist_profile.pk
        assert track.product.price == Decimal('250.00')

    def test_requires_recording_id(
        self,
        artist_client,
        album,
        track_placement_url,
    ):
        """Идентификатор мастер-записи обязателен."""
        response = artist_client.post(
            track_placement_url(album),
            {'price': '100.00'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'recording_id' in response.data
        assert not album.tracks.exists()

    def test_rejects_unknown_recording(
        self,
        artist_client,
        album,
        track_placement_url,
    ):
        """Неизвестный recording_id отклоняется сериализатором."""
        response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': 999999999,
                'price': '100.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'recording_id' in response.data
        assert not album.tracks.exists()

    def test_rejects_recording_without_audio(
        self,
        artist_client,
        artist_user,
        album,
        track_placement_url,
    ):
        """Не создаёт размещение для записи без оригинала."""
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            audio_file='',
        )

        response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '100.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not album.tracks.exists()

    def test_rejects_negative_price(
        self,
        artist_client,
        album,
        recording,
        track_placement_url,
    ):
        """Отрицательная цена не проходит валидацию API."""
        response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '-10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'price' in response.data
        assert not album.tracks.exists()

    def test_single_rejects_individual_price(
        self,
        artist_client,
        artist_user,
        recording,
        track_placement_url,
    ):
        """Для сингла индивидуальная цена трека запрещена."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            created_by=artist_user,
            release_type=Album.ReleaseType.SINGLE,
            is_published=False,
        )

        response = artist_client.post(
            track_placement_url(album),
            {
                'recording_id': recording.pk,
                'price': '100.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not album.tracks.exists()
