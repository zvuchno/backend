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

from users.models import ArtistProfile

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
def staff_user(user_factory):
    """Администратор (видит всё)."""
    return user_factory(
        email='staff@test.com',
        username='staff',
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def artist_user(user_factory):
    """Пользователь-Артист."""
    user = user_factory(
        email='artist@test.com',
        username='artist_user',
    )
    return ArtistProfile.objects.create(
        user=user,
        name='Test_Artist',
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


# =================================
# URL fixtures
# =================================
@pytest.fixture
def login_url():
    """Возвращает URL-адрес эндпоинта для создания токена авторизации."""
    return reverse('api:users:token_create')
