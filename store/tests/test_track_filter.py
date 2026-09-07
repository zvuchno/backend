"""Базовые тесты на фильтрацию и сортировку треков."""

import pytest
from rest_framework import status

from store.models import Genre


@pytest.mark.django_db
class TestTrackFilters:
    """Тестирование фильтров, поиска и сортировки треков артиста."""

    @pytest.fixture
    def tracks(self, variant_factory, artist_user):
        """Создаём треки, принадлежащие альбомам одного артиста."""
        # Жанры
        rock, _ = Genre.objects.get_or_create(
            name='Rock',
            defaults={'slug': 'rock'},
        )
        jazz, _ = Genre.objects.get_or_create(
            name='Jazz',
            defaults={'slug': 'jazz'},
        )

        v1 = variant_factory(
            product_type='track',
            name='Song A',
            artist=artist_user.artist_profile,
            created_by=artist_user,
        )
        t1 = v1.product.track
        t1.album.genre = rock
        t1.album.artist = artist_user.artist_profile
        t1.album.payout_recipient = artist_user
        t1.album.save()

        v2 = variant_factory(
            product_type='track',
            name='Song B',
            artist=artist_user.artist_profile,
            created_by=artist_user,
        )
        t2 = v2.product.track
        t2.album.genre = jazz
        t2.album.artist = artist_user.artist_profile
        t2.album.payout_recipient = artist_user
        t2.album.save()

        return {
            'track_1': t1,
            'track_2': t2,
            'rock': rock,
            'jazz': jazz,
        }

    def test_track_artist_is_derived_from_album(self, tracks):
        """Артист трека определяется Артистом его альбома."""
        track = tracks['track_1']

        assert track.artist == track.album.artist

    def test_filter_by_genre(self, tracks, track_list_url, artist_client):
        """Фильтр по жанру (slug)."""
        response = artist_client.get(
            track_list_url,
            {'genre': tracks['rock'].slug},
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']

        assert len(results) == 1
        assert results[0]['name'] == tracks['track_1'].name

    def test_filter_by_artist(self, tracks, track_list_url, artist_client):
        """Фильтр по slug артиста."""
        response = artist_client.get(
            track_list_url,
            {'artist': tracks['track_1'].album.artist.slug},
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']

        assert len(results) == 2

    def test_search_by_name(self, tracks, track_list_url, artist_client):
        """Поиск по названию трека."""
        response = artist_client.get(
            track_list_url,
            {'search': 'Song A'},
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']

        assert len(results) == 1
        assert results[0]['name'] == tracks['track_1'].name

    def test_ordering_by_name(self, tracks, track_list_url, artist_client):
        """Сортировка по имени."""
        response = artist_client.get(
            track_list_url,
            {'ordering': 'name'},
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']

        assert len(results) == 2
        assert results[0]['name'] == 'Song A'
        assert results[1]['name'] == 'Song B'
