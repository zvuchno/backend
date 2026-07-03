"""Тесты социальной аутентификации."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from allauth.socialaccount.models import SocialAccount
from django.db import IntegrityError
from django.test import RequestFactory

from users.adapters import SocialAccountAdapter
from users.constants import (
    SOCIAL_AUTH_ERROR_BLOCKED_USER,
    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
    SOCIAL_AUTH_ERROR_MISSING_EMAIL,
    SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
)
from users.exceptions import SocialAuthException
from users.models import ListenerProfile
from users.services import SocialAuthService
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


YANDEX_PROVIDER = 'yandex'
VK_PROVIDER = 'vk'


@pytest.fixture
def social_auth_service():
    """Возвращает сервис социальной аутентификации."""
    return SocialAuthService()


class TestSocialAuthService:
    """Тесты обработки пользователя после входа через соцсеть."""

    def test_creates_new_passwordless_user_from_trusted_social_email(
        self,
        social_auth_service,
    ):
        """Создаёт пользователя, подтверждает email от доверенного provider."""
        user = social_auth_service.resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1001',
            email='  New.User@Example.Test ',
            is_email_verified=True,
        )

        assert user.email == 'new.user@example.test'
        assert user.is_email_verified is True
        assert user.has_usable_password() is False

        assert ListenerProfile.objects.filter(
            user=user,
            is_active=True,
        ).exists()

    def test_creates_new_unverified_user_from_untrusted_social_email(
        self,
        social_auth_service,
    ):
        """Не подтверждает email, если provider не считает его доверенным."""
        user = social_auth_service.resolve_user(
            provider=VK_PROVIDER,
            provider_uid='vk-1002',
            email='new.user@example.test',
            is_email_verified=False,
        )

        assert user.email == 'new.user@example.test'
        assert user.is_email_verified is False
        assert user.has_usable_password() is False

        assert ListenerProfile.objects.filter(
            user=user,
            is_active=True,
        ).exists()

    def test_confirms_existing_unverified_user_from_trusted_social_email(
        self,
        social_auth_service,
    ):
        """Подтверждает email существующего пользователя через соцсеть."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )

        resolved_user = social_auth_service.resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1003',
            email='LISTENER@EXAMPLE.TEST',
            is_email_verified=True,
        )

        assert resolved_user.pk == user.pk

        user.refresh_from_db()
        assert user.is_email_verified is True

    def test_rejects_existing_unverified_user_from_untrusted_social_email(
        self,
        social_auth_service,
    ):
        """Не пускает в неподтверждённый аккаунт без доверенного email."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            social_auth_service.resolve_user(
                provider=VK_PROVIDER,
                provider_uid='vk-1004',
                email=user.email,
                is_email_verified=False,
            )

        assert (
            exc_info.value.error_code == SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED
        )

        user.refresh_from_db()
        assert user.is_email_verified is False

    def test_returns_existing_verified_user_by_email(
        self,
        social_auth_service,
    ):
        """Возвращает существующий подтверждённый аккаунт без дубля."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=True,
        )

        resolved_user = social_auth_service.resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1005',
            email=user.email,
            is_email_verified=True,
        )

        assert resolved_user.pk == user.pk
        assert type(user).objects.filter(email=user.email).count() == 1

    def test_returns_user_found_by_existing_social_account(
        self,
        social_auth_service,
    ):
        """Повторный вход через привязанную соцсеть возвращает того же user."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )
        SocialAccount.objects.create(
            user=user,
            provider=YANDEX_PROVIDER,
            uid='yandex-1006',
            extra_data={},
        )

        resolved_user = social_auth_service.resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1006',
            email=user.email,
            is_email_verified=True,
        )

        assert resolved_user.pk == user.pk

        user.refresh_from_db()
        assert user.is_email_verified is True

    def test_rejects_social_login_without_email(
        self,
        social_auth_service,
    ):
        """Не создаёт аккаунт, если provider не вернул email."""
        with pytest.raises(SocialAuthException) as exc_info:
            social_auth_service.resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1007',
                email='',
                is_email_verified=True,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_MISSING_EMAIL

    def test_rejects_blocked_user_found_by_email(
        self,
        social_auth_service,
    ):
        """Не позволяет войти в заблокированный аккаунт по совпавшему email."""
        user = UserFactory(
            email='listener@example.test',
            is_active=False,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            social_auth_service.resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1008',
                email=user.email,
                is_email_verified=True,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_BLOCKED_USER

    def test_rejects_blocked_user_found_by_social_account(
        self,
        social_auth_service,
    ):
        """Не позволяет войти в заблокированный аккаунт."""
        user = UserFactory(is_active=False)
        SocialAccount.objects.create(
            user=user,
            provider=YANDEX_PROVIDER,
            uid='yandex-1009',
            extra_data={},
        )

        with pytest.raises(SocialAuthException) as exc_info:
            social_auth_service.resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1009',
                email=user.email,
                is_email_verified=True,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_BLOCKED_USER


@pytest.fixture
def request_factory():
    """Возвращает фабрику HTTP-запросов."""
    return RequestFactory()


def build_sociallogin(
    *,
    provider: str,
    uid: str,
    email: str,
    save: Mock | None = None,
):
    """Создает минимальный объект SocialLogin для adapter-теста."""
    provider_obj = object()

    account = SimpleNamespace(
        provider=provider,
        uid=uid,
        get_provider=lambda: provider_obj,
    )

    sociallogin = SimpleNamespace(
        account=account,
        user=SimpleNamespace(email=email),
    )
    sociallogin.save = save or Mock()

    return sociallogin


class TestSocialAccountAdapter:
    """Тесты custom adapter-а соцавторизации."""

    def test_pre_social_login_confirms_existing_user_email(
        self,
        monkeypatch,
        request_factory,
    ):
        """Подтверждает email пользователя от trusted provider."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )
        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-1001',
            email='listener@example.test',
        )

        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        adapter.pre_social_login(
            request_factory.post('/api/v1/auth/social/yandex/'),
            sociallogin,
        )

        user.refresh_from_db()
        assert user.is_email_verified is True

    def test_pre_social_login_does_not_confirm_untrusted_email(
        self,
        monkeypatch,
        request_factory,
    ):
        """Не подтверждает email, если provider не считает его trusted."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )
        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-1002',
            email=user.email,
        )

        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: False,
        )

        adapter.pre_social_login(
            request_factory.post('/api/v1/auth/social/yandex/'),
            sociallogin,
        )

        user.refresh_from_db()
        assert user.is_email_verified is False

    def test_pre_social_login_rejects_blocked_existing_user(
        self,
        request_factory,
    ):
        """Не разрешает social login заблокированному пользователю."""
        user = UserFactory(
            email='blocked@example.test',
            is_active=False,
        )
        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-1003',
            email=user.email,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            adapter.pre_social_login(
                request_factory.post('/api/v1/auth/social/yandex/'),
                sociallogin,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_BLOCKED_USER

    def test_save_user_resolves_user_and_saves_sociallogin(
        self,
        monkeypatch,
        request_factory,
    ):
        """Передает пользователя в SocialLogin и сохраняет связь."""
        resolved_user = UserFactory()
        service = Mock()
        service.resolve_user.return_value = resolved_user

        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-1004',
            email='listener@example.test',
        )
        request = request_factory.post('/api/v1/auth/social/yandex/')

        monkeypatch.setattr(adapter, 'get_service', lambda: service)
        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        result = adapter.save_user(request, sociallogin)

        assert result is resolved_user
        assert sociallogin.user is resolved_user

        service.resolve_user.assert_called_once_with(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1004',
            email='listener@example.test',
            is_email_verified=True,
        )
        sociallogin.save.assert_called_once_with(request)

    def test_save_user_returns_service_domain_error_for_api_request(
        self,
        monkeypatch,
        request_factory,
    ):
        """Не заменяет доменную ошибку сервиса общей OAuth-ошибкой."""
        service = Mock()
        service.resolve_user.side_effect = SocialAuthException(
            SOCIAL_AUTH_ERROR_MISSING_EMAIL,
            'Email не получен.',
        )

        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-1005',
            email='',
        )

        monkeypatch.setattr(adapter, 'get_service', lambda: service)
        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            adapter.save_user(
                request_factory.post('/api/v1/auth/social/yandex/'),
                sociallogin,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_MISSING_EMAIL
        sociallogin.save.assert_not_called()

    def test_save_user_returns_social_save_error_when_link_cannot_be_saved(
        self,
        monkeypatch,
        request_factory,
    ):
        """Возвращает понятную ошибку, если SocialAccount не сохранился."""
        resolved_user = UserFactory()
        service = Mock()
        service.resolve_user.return_value = resolved_user

        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-1006',
            email='listener@example.test',
            save=Mock(side_effect=IntegrityError),
        )
        adapter = SocialAccountAdapter()

        monkeypatch.setattr(adapter, 'get_service', lambda: service)
        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            adapter.save_user(
                request_factory.post('/api/v1/auth/social/yandex/'),
                sociallogin,
            )

        assert (
            exc_info.value.error_code == SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED
        )
