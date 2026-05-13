"""Тесты API юридических данных артиста."""

import pytest
from rest_framework import status

from users.models import (
    ArtistLegalProfile,
)

pytestmark = pytest.mark.django_db


class TestArtistLegalProfileAPI:
    """Тесты эндпоинта юридических данных артиста."""

    def test_artist_can_get_non_existent_legal_profile_with_fields(
        self,
        artist_user,
        artist_client,
        artist_legal_url,
    ):
        """Артист получит не пустой объект при отсутствии юр профиля."""
        artist_user.phone = '+71234560000'
        artist_user.save(update_fields=['phone'])
        response = artist_client.get(artist_legal_url)
        assert response.status_code == status.HTTP_200_OK
        assert 'legal_profile' in response.data
        assert 'identity_data' in response.data
        assert 'bank_data' in response.data
        assert 'company_data' in response.data
        assert artist_user.email == response.data['legal_profile']['email']
        assert (
            str(artist_user.phone) == response.data['legal_profile']['phone']
        )
        assert not ArtistLegalProfile.objects.filter(user=artist_user).exists()

    def test_artist_can_get_existent_legal_profile(
        self,
        artist_user,
        artist_client,
        artist_legal_url,
        artist_legal_profile_factory,
    ):
        """Артист получает существующий профиль."""
        legal_profile = artist_legal_profile_factory(user=artist_user)
        response = artist_client.get(artist_legal_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['legal_profile']['email'] == legal_profile.email
        assert response.data['legal_profile']['recipient_type'] == (
            legal_profile.recipient_type
        )
        assert response.data['identity_data'] is not None
        assert response.data['bank_data'] is not None
        assert response.data['company_data'] is None
        assert (
            ArtistLegalProfile.objects.get(
                user=artist_user,
            )
            == legal_profile
        )

    def test_other_artist_cannot_get_artist_legal_profile(
        self,
        artist_user,
        other_artist_user,
        artist_legal_profile_factory,
        other_artist_client,
        artist_legal_url,
    ):
        """Другой артист не получает чужие юридические данные."""
        legal_profile = artist_legal_profile_factory(user=artist_user)
        response = other_artist_client.get(artist_legal_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['legal_profile']['email'] != (legal_profile.email)
        assert response.data['legal_profile']['email'] == (
            other_artist_user.email
        )
        assert response.data['identity_data'] is None
        assert response.data['bank_data'] is None
        assert response.data['company_data'] is None

    def test_not_artist_cannot_get_artist_legal_profile(
        self,
        listener_client,
        artist_legal_url,
    ):
        """Не артист не может получить юр. профиль."""
        response = listener_client.get(artist_legal_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anon_cant_get_artist_legal_profile(
        self,
        artist_legal_url,
        api_client,
    ):
        """Анон не может получить юр данные."""
        response = api_client.get(artist_legal_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_can_get_recipient_types(
        self,
        auth_client,
        artist_recipient_type_url,
    ):
        """Аутентифицированный пользователь может получить типы получателей."""
        response = auth_client.get(artist_recipient_type_url)

        # Минимум эти не должны быть изменены.
        expected_types = [
            {'value': '', 'label': 'Не указано'},
            {'value': 'individual_entrepreneur', 'label': 'ИП'},
            {'value': 'self_employed', 'label': 'СМЗ'},
            {'value': 'legal_entity', 'label': 'Юридическое лицо'},
        ]
        assert response.status_code == status.HTTP_200_OK
        for item in expected_types:
            assert item in response.data

    def test_anonymous_cannot_get_recipient_types(
        self,
        api_client,
        artist_recipient_type_url,
    ):
        """Аноним не может получить типы получателей."""
        response = api_client.get(artist_recipient_type_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
