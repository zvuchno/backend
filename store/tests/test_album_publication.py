"""Тесты правил публикации альбомов."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from store.models import Album, Track
from store.tests.factories import (
    AlbumFactory,
    GenreFactory,
    make_audio_file,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def album_create_payload():
    """Возвращает данные для создания альбома."""
    genre = GenreFactory()

    return {
        'name': 'Тестовый альбом',
        'is_single': False,
        'release_date': '2026-01-01',
        'genre': genre.id,
        'price': '500.00',
        'description': 'Описание альбома.',
        'allow_overpay': False,
        'visibility': 'public',
    }


def test_can_create_album_as_draft_without_tracks(
    artist_client,
    ready_artist_user,
    album_list_url,
    album_create_payload,
):
    """Пустой альбом можно создать как черновик."""
    album_create_payload['is_published'] = False

    response = artist_client.post(
        album_list_url,
        album_create_payload,
        format='json',
    )

    assert response.status_code == HTTPStatus.CREATED

    album = Album.objects.get(name='Тестовый альбом')

    assert album.is_published is False
    assert album.artist == ready_artist_user.artist_profile


def test_cannot_create_published_album_without_tracks(
    artist_client,
    album_list_url,
    album_create_payload,
):
    """Нельзя сразу создать опубликованный альбом без треков."""
    album_create_payload['is_published'] = True

    response = artist_client.post(
        album_list_url,
        album_create_payload,
        format='json',
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.data == {
        'is_published': [
            'Нельзя опубликовать релиз без загруженных треков.',
        ],
    }
    assert not Album.objects.filter(name='Тестовый альбом').exists()


def test_cannot_publish_album_without_tracks(
    artist_client,
    ready_artist_user,
):
    """Пустой альбом нельзя перевести из черновика в опубликованный."""
    album = AlbumFactory(
        artist=ready_artist_user.artist_profile,
        payout_recipient=ready_artist_user,
        created_by=ready_artist_user,
        is_published=False,
    )

    url = reverse(
        'api:store:albums-detail',
        args=(album.id,),
    )

    response = artist_client.patch(
        url,
        {'is_published': True},
        format='json',
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.data == {
        'is_published': [
            'Нельзя опубликовать релиз без загруженных треков.',
        ],
    }

    album.refresh_from_db()
    assert album.is_published is False


def test_cannot_publish_album_with_pending_track(
    artist_client,
    ready_artist_user,
):
    """Нельзя публиковать альбом с незавершённой загрузкой трека."""
    album = AlbumFactory(
        artist=ready_artist_user.artist_profile,
        payout_recipient=ready_artist_user,
        created_by=ready_artist_user,
        is_published=False,
    )
    Track.objects.create(
        album=album,
        created_by=ready_artist_user,
        name='Незагруженный трек',
        position=1,
        is_active=True,
        audio_file=None,
    )

    url = reverse(
        'api:store:albums-detail',
        args=(album.id,),
    )

    response = artist_client.patch(
        url,
        {'is_published': True},
        format='json',
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST

    album.refresh_from_db()
    assert album.is_published is False


def test_cannot_publish_album_with_only_inactive_track(
    artist_client,
    ready_artist_user,
):
    """Неактивный трек не позволяет опубликовать альбом."""
    album = AlbumFactory(
        artist=ready_artist_user.artist_profile,
        payout_recipient=ready_artist_user,
        created_by=ready_artist_user,
        is_published=False,
    )
    Track.objects.create(
        album=album,
        created_by=ready_artist_user,
        name='Неактивный трек',
        position=1,
        audio_file=make_audio_file(),
        is_active=False,
    )

    url = reverse(
        'api:store:albums-detail',
        args=(album.id,),
    )

    response = artist_client.patch(
        url,
        {'is_published': True},
        format='json',
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST

    album.refresh_from_db()
    assert album.is_published is False


def test_can_publish_album_with_uploaded_active_track(
    artist_client,
    ready_artist_user,
):
    """Альбом с загруженным активным треком можно опубликовать."""
    album = AlbumFactory(
        artist=ready_artist_user.artist_profile,
        payout_recipient=ready_artist_user,
        created_by=ready_artist_user,
        is_published=False,
    )
    Track.objects.create(
        album=album,
        created_by=ready_artist_user,
        name='Тестовый трек',
        position=1,
        audio_file=make_audio_file(),
        is_active=True,
    )

    url = reverse(
        'api:store:albums-detail',
        args=(album.id,),
    )

    response = artist_client.patch(
        url,
        {'is_published': True},
        format='json',
    )

    assert response.status_code == HTTPStatus.OK

    album.refresh_from_db()
    assert album.is_published is True


def test_deleting_last_track_unpublishes_album(
    artist_client,
    ready_artist_user,
):
    """Удаление последнего трека снимает альбом с публикации."""
    album = AlbumFactory(
        artist=ready_artist_user.artist_profile,
        payout_recipient=ready_artist_user,
        created_by=ready_artist_user,
        is_published=True,
    )
    track = Track.objects.create(
        album=album,
        created_by=ready_artist_user,
        name='Последний трек',
        position=1,
        audio_file=make_audio_file(),
        is_active=True,
    )

    url = reverse(
        'api:store:tracks-detail',
        args=(track.id,),
    )

    response = artist_client.delete(url)

    assert response.status_code == HTTPStatus.NO_CONTENT

    album.refresh_from_db()
    track.refresh_from_db()

    assert track.is_active is False
    assert album.is_published is False


def test_deleting_one_of_multiple_tracks_keeps_album_published(
    artist_client,
    ready_artist_user,
):
    """Удаление не последнего трека не снимает альбом с публикации."""
    album = AlbumFactory(
        artist=ready_artist_user.artist_profile,
        payout_recipient=ready_artist_user,
        created_by=ready_artist_user,
        is_published=True,
    )
    track = Track.objects.create(
        album=album,
        created_by=ready_artist_user,
        name='Первый трек',
        position=1,
        audio_file=make_audio_file(),
        is_active=True,
    )
    Track.objects.create(
        album=album,
        created_by=ready_artist_user,
        name='Второй трек',
        position=2,
        audio_file=make_audio_file(),
        is_active=True,
    )

    url = reverse(
        'api:store:tracks-detail',
        args=(track.id,),
    )

    response = artist_client.delete(url)

    assert response.status_code == HTTPStatus.NO_CONTENT

    album.refresh_from_db()

    assert album.is_published is True
