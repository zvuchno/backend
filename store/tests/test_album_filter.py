"""Базовые тесты на фильтрацию и сортировку альбомов."""

import datetime

import pytest
from django.utils import timezone
from rest_framework import status

from store.models import Album, Genre
from users.models import ArtistProfile


@pytest.mark.django_db
class TestAlbumFilters:
    """Тестирование функционала фильтрации, поиска и сортировки альбомов."""

    @pytest.fixture
    def albums(self, variant_factory, user, other_user):
        """Создаём альбомы с разными владельцами и жанрами."""
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
            defaults={'name': 'Viktor Tsoi'},
        )
        ArtistProfile.objects.get_or_create(
            user=other_user,
            defaults={'name': 'Boris'},
        )
        # Время для стабильной сортировки
        now = timezone.now()

        v1 = variant_factory(product_type='album', name='Star')
        a1 = v1.product.album
        a1.genre = rock
        a1.save()
        Album.objects.filter(id=a1.id).update(
            created_at=now - datetime.timedelta(days=1),
        )  # старый

        v2 = variant_factory(product_type='album', name='Breath')
        a2 = v2.product.album
        a2.genre = jazz
        a2.owner = other_user
        a2.save()

        return {'album_1': a1, 'album_2': a2, 'rock': rock, 'jazz': jazz}

    def test_filter_by_artist_name(self, albums, album_list_url, api_client):
        """Фильтр по имени артиста."""
        response = api_client.get(album_list_url, {'artist_name': 'viktor'})

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['name'] == albums['album_1'].name

    def test_filter_by_genre(self, albums, album_list_url, api_client):
        """Фильтр по жанру."""
        genre_id = albums['rock'].id
        response = api_client.get(album_list_url, {'genre': genre_id})

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['name'] == albums['album_1'].name

    def test_empty_result_for_invalid_artist(
        self,
        albums,
        album_list_url,
        api_client,
    ):
        """Несуществующий артист возвращает пустой список."""
        response = api_client.get(album_list_url, {'artist_name': 'Ghost'})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == []

    def test_search_by_genre_name(self, albums, album_list_url, api_client):
        """Проверка SearchFilter по имени жанра."""
        response = api_client.get(album_list_url, {'search': 'Rock'})
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == albums['album_1'].name

    def test_ordering_by_name(self, albums, album_list_url, api_client):
        """Сортировка по алфавиту (название)."""
        response = api_client.get(album_list_url, {'ordering': 'name'})
        results = response.data['results']
        assert results[0]['name'] == 'Breath'
        assert results[1]['name'] == 'Star'

    def test_ordering_by_created(self, albums, album_list_url, api_client):
        """Сортировка по дате создания: новые сверху."""
        response = api_client.get(album_list_url, {'ordering': '-created_at'})
        assert response.status_code == status.HTTP_200_OK

        results = response.data['results']
        # Новый альбом должен идти первым
        assert results[0]['name'] == albums['album_2'].name
        assert results[1]['name'] == albums['album_1'].name
