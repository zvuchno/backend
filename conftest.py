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

User = get_user_model()


# =================================
# User fixtures
# =================================
@pytest.fixture
def user(db):
    """Тестовый пользователь."""
    password = 'Pas12345'
    user = User.objects.create_user(
        email='test@zvuchno.com',
        username='Zvuchno_tester',
        password=password,
    )
    user.raw_password = password
    return user


@pytest.fixture
def api_client(db):
    """Обычный клиент для анонимных запросов."""
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Клиент с уже подложенным JWT токеном."""
    api_client.force_authenticate(user=user)
    return api_client


# =================================
# URL fixtures
# =================================
@pytest.fixture
def login_url():
    """Возвращает URL-адрес эндпоинта для создания токена авторизации."""
    return reverse('api:users:token_create')
