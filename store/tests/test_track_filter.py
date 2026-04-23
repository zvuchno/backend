"""Базовые тесты на фильтрацию и сортировку треков."""

import pytest
from rest_framework import status

from store.models import Genre
from users.models import ArtistProfile


@pytest.mark.django_db
class TestTrackFilters:
    """Тестирование фильтров, поиска и сортировки треков."""

    @pytest.fixture
    def tracks(self, variant_factory, user, other_user):
        """Создаём треки с разными альбомами, жанрами и артистами."""
        # Жанры
        rock, _ = Genre.objects.get_or_create(
            name='Rock',
            defaults={'slug': 'rock'},
        )
        jazz, _ = Genre.objects.get_or_create(
            name='Jazz',
            defaults={'slug': 'jazz'},
        )

        # Профили артистов
        ArtistProfile.objects.get_or_create(
            user=user,
            defaults={'name': 'Viktor'},
        )
        ArtistProfile.objects.get_or_create(
            user=other_user,
            defaults={'name': 'Boris'},
        )

        v1 = variant_factory(product_type='track', name='Song A')
        t1 = v1.product.track
        t1.album.genre = rock
        t1.album.owner = user
        t1.album.save()

        v2 = variant_factory(product_type='track', name='Song B')
        t2 = v2.product.track
        t2.album.genre = jazz
        t2.album.owner = other_user
        t2.album.save()

        return {
            'track_1': t1,
            'track_2': t2,
            'rock': rock,
            'jazz': jazz,
        }

    def test_filter_by_genre(self, tracks, track_list_url, api_client):
        """Фильтр по жанру (slug)."""
        response = api_client.get(
            track_list_url,
            {'genre': tracks['rock'].slug},
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']

        assert len(results) == 1
        assert results[0]['name'] == tracks['track_1'].name

    def test_filter_by_artist(self, tracks, track_list_url, api_client):
        """Фильтр по slug артиста."""
        response = api_client.get(
            track_list_url,
            {'artist': tracks['track_1'].album.owner.artist_profile.slug},
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']

        assert len(results) == 1
        assert results[0]['name'] == tracks['track_1'].name

    def test_search_by_name(self, tracks, track_list_url, api_client):
        """Поиск по названию трека."""
        response = api_client.get(
            track_list_url,
            {'search': 'Song A'},
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']

        assert len(results) == 1
        assert results[0]['name'] == tracks['track_1'].name

    def test_ordering_by_name(self, tracks, track_list_url, api_client):
        """Сортировка по имени."""
        response = api_client.get(
            track_list_url,
            {'ordering': 'name'},
        )

        results = response.data['results']

        assert results[0]['name'] == 'Song A'
        assert results[1]['name'] == 'Song B'
