"""Фикстуры тестов для приложения users.

Модуль содержит набор переиспользуемых pytest-фикстур,
специфичных для данного приложения.

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

from users.models import (
    ArtistBankData,
    ArtistCompanyData,
    ArtistIdentityData,
    ArtistLegalProfile,
    ArtistProfile,
    ListenerProfile,
)

User = get_user_model()


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


@pytest.fixture
def artist_legal_url():
    """URL юридических данных артиста."""
    return reverse('api:users:artist_legal_profile')


@pytest.fixture
def artist_recipient_type_url():
    """URL справочника типа получателей."""
    return reverse('api:users:recipient_type_list')


@pytest.fixture
def artist_legal_profile_factory():
    """Фабрика полного набора юридических данных артиста."""

    def create_legal_profile(user, **kwargs) -> ArtistLegalProfile:
        legal_profile = ArtistLegalProfile.objects.create(
            user=user,
            email=kwargs.get('email', user.email),
            phone=kwargs.get('phone', '+79998887766'),
            recipient_type=kwargs.get(
                'recipient_type',
                ArtistLegalProfile.RecipientType.SELF_EMPLOYED,
            ),
            is_verified=kwargs.get('is_verified', False),
            comment=kwargs.get('comment', ''),
        )
        ArtistIdentityData.objects.create(
            legal_profile=legal_profile,
            first_name='Иван',
            last_name='Иванов',
            middle_name='Иванович',
            birth_date='1990-01-01',
            registration_address='г. Москва',
            passport_series='1234',
            passport_number='123456',
            passport_issued_by='500000',
            passport_issue_date='2010-01-01',
            inn='123456789012',
        )
        ArtistBankData.objects.create(
            legal_profile=legal_profile,
            bank_name='Тест-Банк',
            bik='123456789',
            correspondent_account='12345678901234567890',
            checking_account='12345678901234567890',
        )

        if kwargs.get('with_company_data', False):
            ArtistCompanyData.objects.create(
                legal_profile=legal_profile,
                company_name='ООО Тест',
                company_address='г. Москва',
                inn='1234567890',
                ogrn='1234567890123',
            )

        return legal_profile

    return create_legal_profile


@pytest.fixture
def legal_profile_payload():
    """Payload юридического профиля."""
    return {
        'legal_profile': {
            'email': 'legal1@artist.ru',
            'phone': '+79991234567',
            'recipient_type': 'self_employed',
        },
    }


@pytest.fixture
def identity_data_payload():
    """Payload паспортных данных."""
    return {
        'identity_data': {
            'first_name': 'Иван1',
            'last_name': 'Иванов1',
            'middle_name': 'Иванович1',
            'birth_date': '1990-12-01',
            'registration_address': 'г. Москва1',
            'passport_series': '0001',
            'passport_number': '000001',
            'passport_issued_by': '111111',
            'passport_issue_date': '2010-12-01',
            'inn': '123456789011',
        },
    }


@pytest.fixture
def bank_data_payload():
    """Payload банковских данных."""
    return {
        'bank_data': {
            'bank_name': 'Тест-Банк1',
            'bik': '123456781',
            'correspondent_account': '12345678901234567891',
            'checking_account': '12345678901234567891',
        },
    }


@pytest.fixture
def company_data_payload():
    """Payload данных юридического лица."""
    return {
        'company_data': {
            'company_name': 'ООО Тест1',
            'company_address': 'г. Москва1',
            'inn': '1234567891',
            'ogrn': '1234567890121',
        },
    }
