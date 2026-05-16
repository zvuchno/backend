"""Конфигурация тестов pytest.

Модуль содержит общие фикстуры, хуки и настройки,
которые автоматически применяются ко всем тестам проекта.

Используется для:
- создания тестовых объектов (модели, пользователи и т.д.);
- подготовки состояния базы данных;
- генерации входных данных для тестов;
- упрощения и устранения дублирования в тестах.

Файл не требует явного импорта — pytest находит его автоматически.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import ArtistProfile, ListenerProfile

User = get_user_model()


# =================================
# User fixtures
# =================================
@pytest.fixture
def user_factory(db):
    """Фабрика для создания пользователей."""

    def create_user(**kwargs) -> User:
        password = kwargs.pop('password', 'Pas12345')
        defaults = {
            'email': 'user@test.com',
            'username': 'user',
        }
        defaults.update(kwargs)
        user = User.objects.create_user(password=password, **defaults)
        user.raw_password = password
        return user

    return create_user


@pytest.fixture
def artist_user_factory(user_factory):
    """Фабрика пользователей-артистов."""

    def create_artist_user(
        name='Test Artist',
        is_active=True,
        **kwargs,
    ) -> User:
        user = user_factory(**kwargs)
        ArtistProfile.objects.create(
            user=user,
            name=name,
            is_active=is_active,
        )
        return user

    return create_artist_user


@pytest.fixture
def listener_user_factory(user_factory):
    """Фабрика пользователей-слушателей."""

    def create_listener_user(
        full_name='Test Listener',
        is_active=True,
        **kwargs,
    ) -> User:
        user = user_factory(**kwargs)
        ListenerProfile.objects.create(
            user=user,
            full_name=full_name,
            is_active=is_active,
        )
        return user

    return create_listener_user


@pytest.fixture
def user(user_factory):
    """Тестовый пользователь."""
    return user_factory()


@pytest.fixture
def other_user(user_factory):
    """Другой пользователь (не владелец объектов)."""
    return user_factory(
        email='other@test.com',
        username='other_user',
    )


@pytest.fixture
def artist_user(artist_user_factory):
    """Пользователь с профилем артиста."""
    return artist_user_factory(
        email='artist@artist.ru',
        username='artist',
    )


@pytest.fixture
def other_artist_user(artist_user_factory):
    """Другой пользователь с профилем артиста."""
    return artist_user_factory(
        email='other_artist@artist.ru',
        username='other_artist',
        name='Other Artist',
    )


@pytest.fixture
def listener_user(listener_user_factory):
    """Пользователь с профилем слушателя."""
    return listener_user_factory(
        email='listener@listener.ru',
        username='listener',
    )


@pytest.fixture
def staff_user(user_factory):
    """Администратор (видит всё)."""
    return user_factory(
        email='staff@test.com',
        username='staff',
        is_staff=True,
        is_superuser=True,
    )


# =================================
# Client fixtures
# =================================
@pytest.fixture
def api_client():
    """Обычный клиент для анонимных запросов."""
    return APIClient()


@pytest.fixture
def client_factory():
    """Фабрика для создания API-клиентов с авторизацией."""

    def create_client(user=None) -> APIClient:
        client = APIClient()
        if user:
            client.force_authenticate(user=user)
        return client

    return create_client


@pytest.fixture
def auth_client(client_factory, user):
    """Клиент авторизованного пользователя."""
    return client_factory(user)


@pytest.fixture
def other_client(client_factory, other_user):
    """Клиент другого пользователя."""
    return client_factory(other_user)


@pytest.fixture
def staff_client(client_factory, staff_user):
    """Клиент администратора."""
    return client_factory(staff_user)


@pytest.fixture
def artist_client(client_factory, artist_user):
    """Клиент артиста."""
    return client_factory(artist_user)


@pytest.fixture
def other_artist_client(client_factory, other_artist_user):
    """Клиент другого артиста."""
    return client_factory(other_artist_user)


@pytest.fixture
def listener_client(client_factory, listener_user):
    """Клиент слушателя."""
    return client_factory(listener_user)


# =================================
# URL fixtures
# =================================
@pytest.fixture
def login_url():
    """Возвращает URL-адрес эндпоинта для создания токена авторизации."""
    return reverse('api:users:token_create')
