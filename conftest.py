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
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import (
    ArtistProfile,
    ArtistProfileType,
    ArtistShippingPoint,
    ListenerProfile,
)
from users.tests.factories import ArtistProfileFactory, LabelUserFactory
from users.tests.helpers import create_artist_legal_profile

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
def artist_profile_factory(db):
    """Фабрика публичных профилей артистов."""

    def create_artist_profile(
        *,
        user=None,
        label=None,
        name='Test Artist',
        is_active=True,
        **kwargs,
    ) -> ArtistProfile:
        return ArtistProfile.objects.create(
            user=user,
            label=label,
            profile_type=ArtistProfileType.ARTIST,
            name=name,
            is_active=is_active,
            **kwargs,
        )

    return create_artist_profile


@pytest.fixture
def label_profile_factory(db):
    """Фабрика публичных профилей лейблов."""

    def create_label_profile(
        *,
        user,
        name='Test Label',
        is_active=True,
        **kwargs,
    ) -> ArtistProfile:
        return ArtistProfile.objects.create(
            user=user,
            profile_type=ArtistProfileType.LABEL,
            name=name,
            is_active=is_active,
            **kwargs,
        )

    return create_label_profile


@pytest.fixture
def artist_user_factory(
    user_factory,
    artist_profile_factory,
):
    """Фабрика пользователей с профилем артиста."""

    def create_artist_user(
        name='Test Artist',
        is_active=True,
        label=None,
        **kwargs,
    ) -> User:
        user = user_factory(**kwargs)

        artist_profile_factory(
            user=user,
            label=label,
            name=name,
            is_active=is_active,
        )

        return user

    return create_artist_user


@pytest.fixture
def label_user_factory(
    user_factory,
    label_profile_factory,
):
    """Фабрика пользователей с профилем лейбла."""

    def create_label_user(
        name='Test Label',
        is_active=True,
        **kwargs,
    ) -> User:
        user = user_factory(**kwargs)

        label_profile_factory(
            user=user,
            name=name,
            is_active=is_active,
        )

        return user

    return create_label_user


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
    """Пользователь с профилем независимого артиста."""
    user = artist_user_factory(
        email='artist@artist.ru',
        username='artist',
    )
    ArtistShippingPoint.objects.create(
        artist=user.artist_profile,
        pvz_code='MSK1',
        city_code='44',
        city='Москва',
        address='ул. Ленина, д. 10',
    )
    return user


@pytest.fixture
def artist_without_shipping_point(artist_user_factory):
    """Создаёт артиста без настроенного ПВЗ отправления."""
    return artist_user_factory(
        email='artist_without_shipping@example.com',
        username='artist_without_shipping',
        name='Artist Without Shipping',
    )


@pytest.fixture
def artist_without_shipping_point_client(
    client_factory,
    artist_without_shipping_point,
):
    """Возвращает API-клиент артиста без ПВЗ отправления."""
    return client_factory(artist_without_shipping_point)


@pytest.fixture
def other_artist_user(artist_user_factory):
    """Другой пользователь с профилем независимого артиста."""
    user = artist_user_factory(
        email='other_artist@artist.ru',
        username='other_artist',
        name='Other Artist',
    )
    ArtistShippingPoint.objects.create(
        artist=user.artist_profile,
        pvz_code='SPB2',
        city_code='137',
        city='Санкт-Петербург',
        address='Невский пр., д. 25',
    )
    return user


@pytest.fixture
def label_user(label_user_factory):
    """Пользователь с профилем лейбла."""
    return label_user_factory(
        email='label@label.ru',
        username='label',
    )


@pytest.fixture
def label_client(client_factory, label_user):
    """Клиент лейбла."""
    return client_factory(label_user)


@pytest.fixture
def label_created_artist(
    label_user,
    artist_profile_factory,
):
    """Артист без аккаунта, созданный лейблом."""
    return artist_profile_factory(
        user=None,
        label=label_user.artist_profile,
        name='Label Artist',
    )


@pytest.fixture
def signed_artist_user(
    artist_user_factory,
    label_user,
):
    """Пользователь-артист, подключённый к лейблу."""
    return artist_user_factory(
        email='signed@artist.ru',
        username='signed_artist',
        name='Signed Artist',
        label=label_user.artist_profile,
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


@pytest.fixture
def ready_artist_factory():
    """Создаёт артиста, готового к публикации цифровых товаров."""

    def create(**kwargs) -> ArtistProfile:
        artist = ArtistProfileFactory(
            user__is_email_verified=True,
            **kwargs,
        )

        create_artist_legal_profile(
            artist.default_payout_recipient,
            is_verified=True,
        )

        return artist

    return create


@pytest.fixture
def ready_physical_artist_factory(
    ready_artist_factory,
):
    """Создаёт артиста, готового к публикации физических товаров."""

    def create(**kwargs) -> ArtistProfile:
        artist = ready_artist_factory(**kwargs)

        ArtistShippingPoint.objects.get_or_create(
            artist=artist,
            defaults={
                'pvz_code': 'TEST-PVZ-001',
                'city_code': '44',
                'city': 'Москва',
                'address': 'ул. Тестовая, д. 2',
            },
        )

        return artist

    return create


@pytest.fixture
def ready_label_factory():
    """Создаёт лейбл, готовый к публикации цифровых товаров."""

    def create(**kwargs) -> User:
        label_user = LabelUserFactory(
            is_email_verified=True,
            **kwargs,
        )

        create_artist_legal_profile(
            label_user,
            is_verified=True,
        )

        return label_user

    return create


@pytest.fixture
def ready_physical_label_factory(
    ready_label_factory,
):
    """Создаёт лейбл, готовый к публикации физических товаров."""

    def create(**kwargs) -> User:
        label_user = ready_label_factory(**kwargs)

        ArtistShippingPoint.objects.get_or_create(
            artist=label_user.artist_profile,
            defaults={
                'pvz_code': 'TEST-LABEL-PVZ-001',
                'city_code': '44',
                'city': 'Москва',
                'address': 'ул. Тестовая, д. 2',
            },
        )

        return label_user

    return create


@pytest.fixture
def ready_artist_user(artist_user):
    """Делает существующего артиста готовым к цифровым продажам."""
    artist_user.is_email_verified = True
    artist_user.save(update_fields=('is_email_verified',))

    create_artist_legal_profile(
        artist_user,
        is_verified=True,
    )

    return artist_user


@pytest.fixture
def ready_label_user(label_user):
    """Делает существующий лейбл готовым к цифровым продажам."""
    label_user.is_email_verified = True
    label_user.save(update_fields=('is_email_verified',))

    create_artist_legal_profile(
        label_user,
        is_verified=True,
    )

    return label_user


@pytest.fixture
def ready_physical_artist_user(ready_artist_user):
    """Делает существующего артиста готовым к физическим продажам."""
    ArtistShippingPoint.objects.get_or_create(
        artist=ready_artist_user.artist_profile,
        defaults={
            'pvz_code': 'TEST-PVZ-001',
            'city_code': '44',
            'city': 'Москва',
            'address': 'ул. Тестовая, д. 1',
        },
    )

    return ready_artist_user


@pytest.fixture
def ready_physical_label_user(ready_label_user):
    """Делает существующий лейбл готовым к физическим продажам."""
    ArtistShippingPoint.objects.get_or_create(
        artist=ready_label_user.artist_profile,
        defaults={
            'pvz_code': 'TEST-LABEL-PVZ-001',
            'city_code': '44',
            'city': 'Москва',
            'address': 'ул. Тестовая, д. 2',
        },
    )

    return ready_label_user


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
def admin_client(staff_user):
    """Клиент авторизованного суперпользователя для Django Admin."""
    client = Client()
    client.force_login(staff_user)
    return client


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


@pytest.fixture
def artist_leave_label_url() -> str:
    """Возвращает URL самостоятельного выхода артиста из лейбла."""
    return reverse('api:users:artist_leave_label')
