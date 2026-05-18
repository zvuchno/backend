"""Базовые тесты на фильтрацию и сортировку альбомов."""

import datetime

import pytest
from django.utils import timezone
from rest_framework import status

from store.models import Album, Genre


@pytest.mark.django_db
class TestAlbumFilters:
    """Тестирование функционала фильтрации, поиска и сортировки альбомов."""

    @pytest.fixture
    def albums(self, variant_factory, other_artist_user):
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
        a2.owner = other_artist_user
        a2.save()

        return {'album_1': a1, 'album_2': a2, 'rock': rock, 'jazz': jazz}

    def test_filter_by_artist_slug(self, albums, album_list_url, api_client):
        """Фильтр по slug артиста."""
        artist_slug = albums['album_1'].owner.artist_profile.slug
        response = api_client.get(album_list_url, {'artist': artist_slug})

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['name'] == albums['album_1'].name

    def test_filter_by_genre_slug(self, albums, album_list_url, api_client):
        """Фильтр по slug жанра."""
        response = api_client.get(album_list_url, {'genre': 'rock'})

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['name'] == albums['album_1'].name

    def test_filter_by_name_icontains(
        self,
        albums,
        album_list_url,
        api_client,
    ):
        """Поиск по части названия альбома."""
        response = api_client.get(album_list_url, {'name': 'sta'})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Star'

    def test_empty_result_for_invalid_slug(
        self,
        albums,
        album_list_url,
        api_client,
    ):
        """Несуществующий slug возвращает пустой список."""
        response = api_client.get(
            album_list_url,
            {'artist': 'non-existent-artist'},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == []

    def test_search_filter(self, albums, album_list_url, api_client):
        """Проверка работы SearchFilter."""
        response = api_client.get(album_list_url, {'search': 'Rock'})
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == albums['album_1'].name

    def test_ordering_by_name(self, albums, album_list_url, api_client):
        """Сортировка по алфавиту."""
        response = api_client.get(album_list_url, {'ordering': 'name'})
        results = response.data['results']
        assert results[0]['name'] == 'Breath'
        assert results[1]['name'] == 'Star'

    def test_ordering_by_created_at_desc(
        self,
        albums,
        album_list_url,
        api_client,
    ):
        """Сортировка: новые сверху."""
        response = api_client.get(album_list_url, {'ordering': '-created_at'})
        results = response.data['results']
        # album_2 создан позже (now), album_1 — день назад
        assert results[0]['name'] == 'Breath'
        assert results[1]['name'] == 'Star'
