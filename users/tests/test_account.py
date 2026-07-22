"""Тесты API текущей учетной записи."""

import pytest
from rest_framework import status

from users.models import ArtistProfileType

pytestmark = pytest.mark.django_db


class TestMeApi:
    """Тесты получения данных текущей учетной записи."""

    def test_listener_returns_null_profile_type(
        self,
        listener_client,
        account_me_url,
    ):
        """Для слушателя тип профессионального профиля отсутствует."""
        response = listener_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_listener'] is True
        assert response.data['is_artist'] is False
        assert response.data['profile_type'] is None

    def test_artist_returns_artist_profile_type(
        self,
        artist_client,
        account_me_url,
    ):
        """Учетная запись артиста возвращает тип профиля артиста."""
        response = artist_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_artist'] is True
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

    def test_label_returns_label_profile_type(
        self,
        label_client,
        account_me_url,
    ):
        """Учетная запись лейбла возвращает тип профиля лейбла."""
        response = label_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_artist'] is True
        assert response.data['profile_type'] == ArtistProfileType.LABEL

    def test_requires_authentication(
        self,
        api_client,
        account_me_url,
    ):
        """Анонимный пользователь не может получить данные учетной записи."""
        response = api_client.get(account_me_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
