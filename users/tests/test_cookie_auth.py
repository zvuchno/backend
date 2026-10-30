"""Тесты cookie-аутентификации."""

import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle

from users.views.cookie_auth import CookieLoginView

pytestmark = pytest.mark.django_db

PASSWORD = 'StrongPassword123!'


@pytest.fixture(autouse=True)
def disable_cookie_login_throttling(monkeypatch):
    """Отключает throttling во всех тестах, кроме его регрессии."""
    monkeypatch.setattr(CookieLoginView, 'throttle_classes', [])


@pytest.fixture
def clear_throttle_cache():
    """Очищает общий throttle cache до и после регрессионного теста."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def cookie_login_url():
    """URL входа через JWT-cookie."""
    return reverse('api:users:cookie_login')


@pytest.fixture
def cookie_refresh_url():
    """URL обновления JWT-cookie."""
    return reverse('api:users:cookie_refresh')


@pytest.fixture
def cookie_logout_url():
    """URL выхода из JWT-cookie."""
    return reverse('api:users:cookie_logout')


@pytest.fixture
def password_user(user):
    """Пользователь с известным паролем."""
    user.set_password(PASSWORD)
    user.save(update_fields=('password',))
    return user


class TestCookieLogin:
    """Тесты входа через JWT-cookie."""

    def test_login_sets_auth_cookies(
        self,
        api_client,
        password_user,
        cookie_login_url,
    ):
        """Успешный вход устанавливает access и refresh cookie."""
        response = api_client.post(
            cookie_login_url,
            data={
                'email': password_user.email,
                'password': PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert settings.REST_AUTH['JWT_AUTH_COOKIE'] in response.cookies
        assert (
            settings.REST_AUTH['JWT_AUTH_REFRESH_COOKIE'] in response.cookies
        )

    def test_login_rejects_invalid_password(
        self,
        api_client,
        password_user,
        cookie_login_url,
    ):
        """Неверный пароль не открывает cookie-сессию."""
        response = api_client.post(
            cookie_login_url,
            data={
                'email': password_user.email,
                'password': 'WrongPassword123!',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert settings.REST_AUTH['JWT_AUTH_COOKIE'] not in response.cookies
        assert (
            settings.REST_AUTH['JWT_AUTH_REFRESH_COOKIE']
            not in response.cookies
        )

    @override_settings(
        PASSWORD_HASHERS=[
            'django.contrib.auth.hashers.ScryptPasswordHasher',
            'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        ],
    )
    def test_login_upgrades_pbkdf2_password_to_scrypt(
        self,
        api_client,
        user,
        cookie_login_url,
    ):
        """При входе старый PBKDF2-хэш обновляется до scrypt."""
        password = 'StrongPassword123!'

        user.password = make_password(
            password,
            hasher='pbkdf2_sha256',
        )
        user.save(update_fields=('password',))

        assert user.password.startswith('pbkdf2_sha256$')

        response = api_client.post(
            cookie_login_url,
            data={
                'email': user.email,
                'password': password,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()

        assert user.password.startswith('scrypt$')
        assert user.check_password(password)

    def test_login_authenticates_following_requests(
        self,
        api_client,
        password_user,
        cookie_login_url,
        account_me_url,
    ):
        """После cookie-login последующие запросы авторизованы."""
        response = api_client.post(
            cookie_login_url,
            data={
                'email': password_user.email,
                'password': PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        response = api_client.get(account_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == password_user.email

    def test_invalid_logins_from_same_ip_are_throttled(
        self,
        api_client,
        password_user,
        cookie_login_url,
        clear_throttle_cache,
        monkeypatch,
    ):
        """Неверные пароли расходуют login-limit и приводят к HTTP 429."""
        monkeypatch.setattr(
            CookieLoginView,
            'throttle_classes',
            [ScopedRateThrottle],
        )
        login_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['login']
        assert login_rate == '5/min'

        request_data = {
            'email': password_user.email,
            'password': 'WrongPassword123!',
        }
        responses = [
            api_client.post(
                cookie_login_url,
                data=request_data,
                format='json',
                REMOTE_ADDR='192.0.2.30',
            )
            for _ in range(6)
        ]

        assert all(
            response.status_code == status.HTTP_400_BAD_REQUEST
            for response in responses[:5]
        )
        assert responses[5].status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert responses[5].data['detail'].code == 'throttled'
        assert all(
            settings.REST_AUTH['JWT_AUTH_COOKIE'] not in response.cookies
            for response in responses
        )
        assert all(
            settings.REST_AUTH['JWT_AUTH_REFRESH_COOKIE']
            not in response.cookies
            for response in responses
        )


class TestCookieRefresh:
    """Тесты обновления JWT-cookie."""

    def test_refresh_uses_refresh_cookie(
        self,
        api_client,
        password_user,
        cookie_login_url,
        cookie_refresh_url,
    ):
        """Refresh-cookie позволяет получить новый access-cookie."""
        login_response = api_client.post(
            cookie_login_url,
            data={
                'email': password_user.email,
                'password': PASSWORD,
            },
            format='json',
        )

        assert login_response.status_code == status.HTTP_200_OK

        response = api_client.post(
            cookie_refresh_url,
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert settings.REST_AUTH['JWT_AUTH_COOKIE'] in response.cookies


class TestCookieLogout:
    """Тесты выхода из cookie-сессии."""

    def test_logout_clears_auth_cookies(
        self,
        api_client,
        password_user,
        cookie_login_url,
        cookie_logout_url,
    ):
        """Выход очищает access и refresh cookie."""
        login_response = api_client.post(
            cookie_login_url,
            data={
                'email': password_user.email,
                'password': PASSWORD,
            },
            format='json',
        )

        assert login_response.status_code == status.HTTP_200_OK

        response = api_client.post(
            cookie_logout_url,
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        assert (
            response.cookies[settings.REST_AUTH['JWT_AUTH_COOKIE']]['max-age']
            == 0
        )

        assert (
            response.cookies[settings.REST_AUTH['JWT_AUTH_REFRESH_COOKIE']][
                'max-age'
            ]
            == 0
        )
