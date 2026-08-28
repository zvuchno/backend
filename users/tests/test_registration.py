"""Тесты API регистрации слушателей и артистов."""

from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.settings import api_settings

from users.consents_policy import ConsentPolicy, ConsentScenario
from users.models import (
    ArtistProfile,
    ArtistProfileType,
    ConsentDocument,
    ListenerProfile,
    UserConsent,
)
from users.views import BaseRegistrationView

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def clear_throttle_cache():
    """Очищает кэш throttling до и после теста."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def disable_registration_throttling(monkeypatch):
    """Отключает throttling для обычных тестов регистрации."""
    monkeypatch.setattr(
        BaseRegistrationView,
        'throttle_classes',
        [],
    )


@pytest.fixture
def verification_email_mock(monkeypatch):
    """Подменяет отправку письма подтверждения email."""
    mock = Mock()

    monkeypatch.setattr(
        'users.views.base_registration.request_email_verification',
        mock,
    )

    return mock


@pytest.fixture
def artist_newsletter_document():
    """Создаёт активное согласие на рекламную рассылку артиста."""
    return ConsentDocument.objects.create(
        document_type=ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
        version='1.0',
        content='Тестовое согласие на рекламную рассылку.',
        is_active=True,
    )


@pytest.mark.usefixtures('disable_registration_throttling')
class TestListenerRegistration:
    """Тесты регистрации слушателя."""

    def test_register_listener_creates_user_and_listener_profile(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        verification_email_mock,
    ):
        """Успешная регистрация создает аккаунт и профиль слушателя."""
        response = api_client.post(
            listener_register_url,
            data=listener_register_payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert 'password' not in response.data

        user = User.objects.get(email=listener_register_payload['email'])

        assert response.data['id'] == user.id
        assert response.data['email'] == listener_register_payload['email']
        assert (
            response.data['username']
            == (listener_register_payload['username'])
        )
        assert response.data['phone'] == listener_register_payload['phone']

        assert user.check_password(listener_register_payload['password'])
        assert not user.is_email_verified
        assert not user.is_phone_verified

        listener_profile = ListenerProfile.objects.get(user=user)
        assert listener_profile.full_name == ''
        assert listener_profile.is_active

        verification_email_mock.assert_called_once_with(user)

    @pytest.mark.parametrize(
        'field,value',
        (
            ('username', ''),
            ('email', 'incorrect-email'),
            ('phone', ''),
            ('password', '123'),
        ),
    )
    def test_register_listener_rejects_invalid_data(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        verification_email_mock,
        field,
        value,
    ):
        """Некорректные обязательные данные не создают пользователя."""
        payload = {
            **listener_register_payload,
            field: value,
        }

        response = api_client.post(
            listener_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert field in response.data
        assert User.objects.count() == 0
        verification_email_mock.assert_not_called()

    @pytest.mark.parametrize(
        'field',
        ('username', 'email', 'phone'),
    )
    def test_register_listener_rejects_duplicate_account_data(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        user_factory,
        verification_email_mock,
        field,
    ):
        """Повторные username, email и телефон отклоняются."""
        existing_user = user_factory(
            username='occupied_username',
            email='occupied@example.test',
            phone='+79990000001',
        )

        payload = {
            **listener_register_payload,
            field: str(getattr(existing_user, field)),
        }

        response = api_client.post(
            listener_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert field in response.data
        assert User.objects.count() == 1
        verification_email_mock.assert_not_called()

    def test_registration_authenticates_listener(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        account_me_url,
        verification_email_mock,
    ):
        """После регистрации слушатель сразу авторизован."""
        response = api_client.post(
            listener_register_url,
            data=listener_register_payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        response = api_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == listener_register_payload['email']

    @override_settings(
        PASSWORD_HASHERS=[
            'django.contrib.auth.hashers.ScryptPasswordHasher',
            'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        ],
    )
    def test_registration_uses_scrypt_password_hasher(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
    ):
        """Пароль нового пользователя хэшируется с помощью scrypt."""
        response = api_client.post(
            listener_register_url,
            data=listener_register_payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(
            email=listener_register_payload['email'],
        )

        assert user.password.startswith('scrypt$')

    def test_register_listener_requires_consents(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        verification_email_mock,
    ):
        """Регистрация слушателя требует согласия на обработку ПДн."""
        payload = listener_register_payload.copy()
        payload.pop('consents')

        response = api_client.post(
            listener_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'consents' in response.data
        assert User.objects.count() == 0
        verification_email_mock.assert_not_called()

    def test_register_listener_saves_consent(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        verification_email_mock,
    ):
        """Регистрация фиксирует согласие слушателя."""
        response = api_client.post(
            listener_register_url,
            data=listener_register_payload,
            format='json',
            REMOTE_ADDR='192.0.2.10',
            HTTP_USER_AGENT='Test Agent',
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(
            email=listener_register_payload['email'],
        )
        consent = UserConsent.objects.get(user=user)

        assert (
            consent.document.document_type
            == ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA
        )
        assert consent.email == user.email
        assert consent.ip_address == '192.0.2.10'
        assert consent.user_agent == 'Test Agent'


@pytest.mark.usefixtures('disable_registration_throttling')
class TestArtistRegistration:
    """Тесты регистрации артиста."""

    def test_register_artist_creates_required_profiles(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        verification_email_mock,
    ):
        """Регистрация артиста создает аккаунт, слушателя и артиста."""
        response = api_client.post(
            artist_register_url,
            data=artist_register_payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert 'password' not in response.data

        user = User.objects.get(email=artist_register_payload['email'])

        assert response.data['id'] == user.id
        assert response.data['email'] == artist_register_payload['email']
        assert (
            response.data['username'] == (artist_register_payload['username'])
        )
        assert response.data['phone'] == artist_register_payload['phone']
        assert response.data['name'] == artist_register_payload['name']

        assert response.data['profile_type'] == ArtistProfileType.ARTIST

        assert user.check_password(artist_register_payload['password'])
        assert not user.is_email_verified
        assert not user.is_phone_verified

        assert ListenerProfile.objects.filter(user=user).exists()

        artist_profile = ArtistProfile.objects.get(user=user)
        assert artist_profile.name == artist_register_payload['name']
        assert artist_profile.profile_type == ArtistProfileType.ARTIST
        assert artist_profile.is_active
        assert artist_profile.slug

        verification_email_mock.assert_called_once_with(user)

    def test_register_artist_requires_name(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        verification_email_mock,
    ):
        """Без имени артиста регистрация не проходит."""
        payload = artist_register_payload.copy()
        payload.pop('name')

        response = api_client.post(
            artist_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'name' in response.data
        assert User.objects.count() == 0
        assert ListenerProfile.objects.count() == 0
        assert ArtistProfile.objects.count() == 0
        verification_email_mock.assert_not_called()

    @pytest.mark.parametrize(
        'field',
        ('username', 'email', 'phone'),
    )
    def test_register_artist_rejects_duplicate_account_data(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        user_factory,
        verification_email_mock,
        field,
    ):
        """Артист не может зарегистрироваться с занятым полем аккаунта."""
        existing_user = user_factory(
            username='occupied_username',
            email='occupied@example.test',
            phone='+79990000001',
        )

        payload = {
            **artist_register_payload,
            field: str(getattr(existing_user, field)),
        }

        response = api_client.post(
            artist_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert field in response.data
        assert User.objects.count() == 1
        assert ListenerProfile.objects.count() == 0
        assert ArtistProfile.objects.count() == 0
        verification_email_mock.assert_not_called()

    def test_register_label_creates_label_profile(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        verification_email_mock,
    ):
        """Регистрация лейбла создает профиль с типом лейбла."""
        payload = {
            **artist_register_payload,
            'profile_type': ArtistProfileType.LABEL,
        }

        response = api_client.post(
            artist_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email=payload['email'])
        artist_profile = ArtistProfile.objects.get(user=user)

        assert response.data['name'] == payload['name']
        assert response.data['profile_type'] == ArtistProfileType.LABEL
        assert artist_profile.name == payload['name']
        assert artist_profile.profile_type == ArtistProfileType.LABEL

        assert ListenerProfile.objects.filter(user=user).exists()
        verification_email_mock.assert_called_once_with(user)

    def test_register_artist_rejects_invalid_profile_type(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        verification_email_mock,
    ):
        """Регистрация отклоняет неизвестный тип профиля."""
        payload = {
            **artist_register_payload,
            'profile_type': 'unknown',
        }

        response = api_client.post(
            artist_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'profile_type' in response.data
        assert User.objects.count() == 0
        assert ListenerProfile.objects.count() == 0
        assert ArtistProfile.objects.count() == 0
        verification_email_mock.assert_not_called()

    def test_register_artist_requires_all_mandatory_consents(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        verification_email_mock,
    ):
        """Регистрация артиста требует все обязательные согласия."""
        payload = {
            **artist_register_payload,
            'consents': [
                ConsentDocument.DocumentType.ARTIST_OFFER,
                ConsentDocument.DocumentType.ARTIST_PERSONAL_DATA,
            ],
        }

        response = api_client.post(
            artist_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'consents' in response.data
        assert User.objects.count() == 0
        verification_email_mock.assert_not_called()

    def test_register_artist_saves_required_consents(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        verification_email_mock,
    ):
        """Регистрация артиста фиксирует обязательные согласия."""
        response = api_client.post(
            artist_register_url,
            data=artist_register_payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email=artist_register_payload['email'])

        consent_types = set(
            UserConsent.objects.filter(user=user).values_list(
                'document__document_type',
                flat=True,
            ),
        )

        assert consent_types == ConsentPolicy.get_required(
            ConsentScenario.ARTIST_ONBOARDING,
        )

    def test_register_artist_accepts_optional_newsletter_consent(
        self,
        api_client,
        artist_register_url,
        artist_register_payload,
        artist_newsletter_document,
        verification_email_mock,
    ):
        """Артист может дополнительно согласиться на рекламную рассылку."""
        payload = {
            **artist_register_payload,
            'consents': [
                *artist_register_payload['consents'],
                ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
            ],
        }

        response = api_client.post(
            artist_register_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email=payload['email'])

        assert UserConsent.objects.filter(
            user=user,
            document__document_type=(
                ConsentDocument.DocumentType.ARTIST_NEWSLETTER
            ),
        ).exists()


class TestRegistrationThrottle:
    """Тесты ограничения частоты регистрации."""

    def test_registration_throttle_uses_ip_for_authenticated_user(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        clear_throttle_cache,
        monkeypatch,
    ):
        """Регистрация ограничивается по IP независимо от авторизации."""
        monkeypatch.setitem(
            api_settings.DEFAULT_THROTTLE_RATES,
            'registration',
            '1/min',
        )

        first_response = api_client.post(
            listener_register_url,
            data=listener_register_payload,
            format='json',
            REMOTE_ADDR='192.0.2.10',
        )

        second_response = api_client.post(
            listener_register_url,
            data={
                **listener_register_payload,
                'username': 'another_listener',
                'email': 'another_listener@example.test',
                'phone': '+79991234568',
            },
            format='json',
            REMOTE_ADDR='192.0.2.10',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_registration_is_throttled(
        self,
        api_client,
        listener_register_url,
        listener_register_payload,
        verification_email_mock,
        clear_throttle_cache,
        monkeypatch,
    ):
        """Повторная регистрация с одного IP ограничивается."""
        monkeypatch.setitem(
            api_settings.DEFAULT_THROTTLE_RATES,
            'registration',
            '1/min',
        )

        first_response = api_client.post(
            listener_register_url,
            data=listener_register_payload,
            format='json',
            REMOTE_ADDR='192.0.2.10',
        )

        second_response = api_client.post(
            listener_register_url,
            data={
                **listener_register_payload,
                'username': 'another_listener',
                'email': 'another_listener@example.test',
                'phone': '+79991234568',
            },
            format='json',
            REMOTE_ADDR='192.0.2.10',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert second_response.data['detail'].code == 'throttled'
