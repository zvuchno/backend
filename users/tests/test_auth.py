"""Тесты API входа по email и паролю."""

from unittest.mock import Mock

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle

from users.models import CoreUser
from users.views.jwt import CustomTokenObtainPairView

pytestmark = pytest.mark.django_db


@pytest.fixture
def login_url():
    """URL входа по email и паролю."""
    return '/api/v1/auth/token/create/'


@pytest.fixture
def clear_throttle_cache():
    """Очищает кэш throttling до и после теста."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def disable_login_throttling(monkeypatch):
    """Отключает throttling для обычных тестов входа."""
    monkeypatch.setattr(
        CustomTokenObtainPairView,
        'throttle_classes',
        [],
    )


@pytest.fixture
def authentication_actions_mock(monkeypatch):
    """Подменяет действия после успешной аутентификации."""
    mock = Mock()

    monkeypatch.setattr(
        'users.serializers.jwt.run_actions_after_authentication',
        mock,
    )

    return mock


@pytest.fixture
def user_with_password(user_factory):
    """Создает пользователя с заданным паролем."""

    def create_user(password='correct-password', **kwargs) -> CoreUser:
        user = user_factory(**kwargs)
        user.set_password(password)
        user.save(update_fields=['password'])
        return user

    return create_user


@pytest.mark.usefixtures('disable_login_throttling')
class TestPasswordLogin:
    """Тесты входа по email и паролю."""

    def test_login_returns_access_and_refresh_tokens(
        self,
        api_client,
        login_url,
        user_with_password,
        authentication_actions_mock,
    ):
        """Корректные email и пароль возвращают пару JWT-токенов."""
        user = user_with_password(
            email='listener@example.test',
            password='correct-password',
        )

        response = api_client.post(
            login_url,
            data={
                'email': user.email,
                'password': 'correct-password',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['access']
        assert response.data['refresh']

        authentication_actions_mock.assert_called_once()

        called_user, called_request = (
            authentication_actions_mock.call_args.args
        )
        assert called_user == user
        assert called_request.path == login_url

    @pytest.mark.parametrize(
        'email,password',
        (
            ('listener@example.test', 'wrong-password'),
            ('unknown@example.test', 'correct-password'),
        ),
    )
    def test_login_rejects_invalid_credentials(
        self,
        api_client,
        login_url,
        user_with_password,
        authentication_actions_mock,
        email,
        password,
    ):
        """Неверные учетные данные не выдают JWT-токены."""
        user_with_password(
            email='listener@example.test',
            password='correct-password',
        )

        response = api_client.post(
            login_url,
            data={
                'email': email,
                'password': password,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
        assert 'refresh' not in response.data
        authentication_actions_mock.assert_not_called()

    def test_login_rejects_inactive_user(
        self,
        api_client,
        login_url,
        user_with_password,
        authentication_actions_mock,
    ):
        """Неактивный пользователь не может получить JWT-токены."""
        user = user_with_password(
            email='blocked@example.test',
            password='correct-password',
            is_active=False,
        )

        response = api_client.post(
            login_url,
            data={
                'email': user.email,
                'password': 'correct-password',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
        assert 'refresh' not in response.data
        authentication_actions_mock.assert_not_called()


class TestLoginThrottle:
    """Тесты ограничения частоты входа."""

    def test_login_is_throttled(
        self,
        api_client,
        login_url,
        user_with_password,
        authentication_actions_mock,
        clear_throttle_cache,
        monkeypatch,
    ):
        """Повторный вход с одного IP ограничивается."""
        user = user_with_password(
            email='listener@example.test',
            password='correct-password',
        )

        monkeypatch.setattr(
            CustomTokenObtainPairView,
            'throttle_classes',
            [ScopedRateThrottle],
        )
        monkeypatch.setitem(
            api_settings.DEFAULT_THROTTLE_RATES,
            'login',
            '1/min',
        )

        first_response = api_client.post(
            login_url,
            data={
                'email': user.email,
                'password': 'correct-password',
            },
            format='json',
            REMOTE_ADDR='192.0.2.20',
        )

        second_response = api_client.post(
            login_url,
            data={
                'email': user.email,
                'password': 'correct-password',
            },
            format='json',
            REMOTE_ADDR='192.0.2.20',
        )

        assert first_response.status_code == status.HTTP_200_OK
        assert second_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert second_response.data['detail'].code == 'throttled'

        authentication_actions_mock.assert_called_once()
