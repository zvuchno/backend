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

    def test_account_me_does_not_return_inactive_artist_role(
        self,
        artist_client,
        artist_user,
        account_me_url,
    ):
        """Выключенный профиль не считается активной ролью артиста."""
        artist = artist_user.artist_profile
        artist.is_active = False
        artist.save(update_fields=('is_active',))

        response = artist_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_artist'] is False
        assert response.data['profile_type'] is None

    def test_account_me_does_not_return_inactive_label_role(
        self,
        label_client,
        label_user,
        account_me_url,
    ):
        """Выключенный профиль не считается активной ролью лейбла."""
        label = label_user.artist_profile
        label.is_active = False
        label.save(update_fields=('is_active',))

        response = label_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_artist'] is False
        assert response.data['profile_type'] is None
        assert response.data['available_profile_upgrades'] == []

    def test_listener_has_artist_and_label_profile_upgrades(
        self,
        listener_client,
        account_me_url,
    ):
        response = listener_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['available_profile_upgrades'] == [
            ArtistProfileType.ARTIST,
            ArtistProfileType.LABEL,
        ]

    def test_independent_artist_can_upgrade_to_label(
        self,
        artist_client,
        account_me_url,
    ):
        response = artist_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['available_profile_upgrades'] == [
            ArtistProfileType.LABEL,
        ]

    def test_managed_artist_has_no_profile_upgrades(
        self,
        client_factory,
        signed_artist_user,
        account_me_url,
    ):
        client = client_factory(signed_artist_user)

        response = client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['available_profile_upgrades'] == []

    def test_label_has_no_profile_upgrades(
        self,
        label_client,
        account_me_url,
    ):
        response = label_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['available_profile_upgrades'] == []

    def test_inactive_artist_has_no_profile_upgrades(
        self,
        artist_client,
        artist_user,
        account_me_url,
    ):
        artist = artist_user.artist_profile
        artist.is_active = False
        artist.save(update_fields=('is_active',))

        response = artist_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_artist'] is False
        assert response.data['profile_type'] is None
        assert response.data['available_profile_upgrades'] == []
