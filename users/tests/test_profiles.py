"""Тесты API профилей артистов и лейблов."""

import pytest
from rest_framework import status

from users.models import ArtistProfile, ArtistProfileType

pytestmark = pytest.mark.django_db


class TestBecomeArtistOrLabelApi:
    """Тесты создания профиля артиста или лейбла слушателем."""

    def test_listener_becomes_artist_by_default(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Без указания типа создается профиль артиста."""
        response = listener_client.post(
            become_artist_url,
            data={'name': 'Новый артист'},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Новый артист'
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

        profile = ArtistProfile.objects.get(user=listener_user)

        assert profile.name == 'Новый артист'
        assert profile.profile_type == ArtistProfileType.ARTIST

    def test_listener_becomes_label(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Слушатель может создать профиль лейбла."""
        response = listener_client.post(
            become_artist_url,
            data={
                'name': 'Новый лейбл',
                'profile_type': ArtistProfileType.LABEL,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Новый лейбл'
        assert response.data['profile_type'] == ArtistProfileType.LABEL

        profile = ArtistProfile.objects.get(user=listener_user)

        assert profile.name == 'Новый лейбл'
        assert profile.profile_type == ArtistProfileType.LABEL

    def test_rejects_invalid_profile_type(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Неизвестный тип профиля отклоняется."""
        response = listener_client.post(
            become_artist_url,
            data={
                'name': 'Неизвестный профиль',
                'profile_type': 'unknown',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'profile_type' in response.data
        assert not ArtistProfile.objects.filter(
            user=listener_user,
        ).exists()

    def test_artist_cannot_create_second_profile(
        self,
        artist_client,
        become_artist_url,
    ):
        """Артист не может создать второй профессиональный профиль."""
        response = artist_client.post(
            become_artist_url,
            data={
                'name': 'Второй профиль',
                'profile_type': ArtistProfileType.LABEL,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_label_cannot_create_second_profile(
        self,
        label_client,
        become_artist_url,
    ):
        """Лейбл не может создать второй профессиональный профиль."""
        response = label_client.post(
            become_artist_url,
            data={
                'name': 'Второй профиль',
                'profile_type': ArtistProfileType.ARTIST,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_requires_authentication(
        self,
        api_client,
        become_artist_url,
    ):
        """Анонимный пользователь не может создать профиль."""
        response = api_client.post(
            become_artist_url,
            data={'name': 'Новый артист'},
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestArtistMeApi:
    """Тесты профиля текущего артиста или лейбла."""

    def test_returns_artist_profile(
        self,
        artist_client,
        artist_me_url,
    ):
        """Возвращает профиль текущего артиста."""
        response = artist_client.get(artist_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

    def test_returns_label_profile(
        self,
        label_client,
        artist_me_url,
    ):
        """Возвращает профиль текущего лейбла."""
        response = label_client.get(artist_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.LABEL


class TestArtistPublicApi:
    """Тесты публичного профиля артиста или лейбла."""

    def test_returns_artist_profile_type(
        self,
        api_client,
        artist_user,
        artist_public_url,
    ):
        """Публичный профиль артиста возвращает его тип."""
        response = api_client.get(
            artist_public_url(artist_user.artist_profile),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

    def test_returns_label_profile_type(
        self,
        api_client,
        label_user,
        artist_public_url,
    ):
        """Публичный профиль лейбла возвращает его тип."""
        response = api_client.get(
            artist_public_url(label_user.artist_profile),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.LABEL
