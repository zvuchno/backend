"""Тесты социальной аутентификации."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from allauth.socialaccount.models import SocialAccount
from django.db import IntegrityError

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


def build_sociallogin(
    *,
    provider: str,
    uid: str,
    email: str,
    save: Mock | None = None,
):
    """Создает минимальный объект SocialLogin для adapter-теста."""
    provider_obj = object()

    sociallogin = SimpleNamespace(
        account=SimpleNamespace(
            provider=provider,
            uid=uid,
            get_provider=lambda: provider_obj,
        ),
        user=SimpleNamespace(
            email=email,
        ),
    )
    sociallogin.save = save if save is not None else Mock()

    return sociallogin


class TestSocialAuthService:
    """Тесты обработки пользователя после входа через соцсеть."""

    def test_creates_new_passwordless_user_from_trusted_social_email(self):
        """Создает passwordless-пользователя с подтвержденным email."""
        user = SocialAuthService().resolve_user(
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

    def test_creates_new_unverified_user_from_untrusted_social_email(self):
        """Не подтверждает email пользователя от недоверенного provider."""
        user = SocialAuthService().resolve_user(
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
    ):
        """Подтверждает email существующего пользователя через соцсеть."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )

        resolved_user = SocialAuthService().resolve_user(
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
    ):
        """Не пускает в неподтвержденный аккаунт без доверенного email."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            SocialAuthService().resolve_user(
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

    def test_does_not_confirm_email_when_social_email_differs(
        self,
    ):
        """Не подтверждает другой email у пользователя с SocialAccount."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )
        SocialAccount.objects.create(
            user=user,
            provider=YANDEX_PROVIDER,
            uid='yandex-1005',
            extra_data={},
        )

        resolved_user = SocialAuthService().resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1005',
            email='another@example.test',
            is_email_verified=True,
        )

        assert resolved_user.pk == user.pk

        user.refresh_from_db()
        assert user.is_email_verified is False

    def test_returns_user_found_by_existing_social_account(self):
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

        resolved_user = SocialAuthService().resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1006',
            email=user.email,
            is_email_verified=True,
        )

        assert resolved_user.pk == user.pk

        user.refresh_from_db()
        assert user.is_email_verified is True

    def test_rejects_social_login_without_email(self):
        """Не создает аккаунт, если provider не вернул email."""
        with pytest.raises(SocialAuthException) as exc_info:
            SocialAuthService().resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1007',
                email='',
                is_email_verified=True,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_MISSING_EMAIL

    def test_rejects_blocked_user_found_by_email(self):
        """Не позволяет войти в заблокированный аккаунт по совпавшему email."""
        user = UserFactory(
            email='listener@example.test',
            is_active=False,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            SocialAuthService().resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1008',
                email=user.email,
                is_email_verified=True,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_BLOCKED_USER

    def test_rejects_blocked_user_found_by_social_account(self):
        """Не позволяет войти в заблокированный аккаунт через SocialAccount."""
        user = UserFactory(is_active=False)
        SocialAccount.objects.create(
            user=user,
            provider=YANDEX_PROVIDER,
            uid='yandex-1009',
            extra_data={},
        )

        with pytest.raises(SocialAuthException) as exc_info:
            SocialAuthService().resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1009',
                email=user.email,
                is_email_verified=True,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_BLOCKED_USER


class TestSocialAccountAdapter:
    """Тесты custom adapter-а социальной аутентификации."""

    def test_pre_social_login_confirms_existing_user_email(
        self,
        monkeypatch,
        rf,
    ):
        """Подтверждает email существующего пользователя до social login."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )
        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-2001',
            email=user.email,
        )

        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        adapter.pre_social_login(
            rf.post('/api/v1/auth/social/yandex/'),
            sociallogin,
        )

        user.refresh_from_db()
        assert user.is_email_verified is True

    def test_pre_social_login_does_not_confirm_untrusted_email(
        self,
        monkeypatch,
        rf,
    ):
        """Не подтверждает email, если provider не считается trusted."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )
        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-2002',
            email=user.email,
        )

        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: False,
        )

        adapter.pre_social_login(
            rf.post('/api/v1/auth/social/yandex/'),
            sociallogin,
        )

        user.refresh_from_db()
        assert user.is_email_verified is False

    def test_pre_social_login_rejects_blocked_existing_user(self, rf):
        """Не разрешает social login заблокированному пользователю."""
        user = UserFactory(
            email='blocked@example.test',
            is_active=False,
        )
        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-2003',
            email=user.email,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            adapter.pre_social_login(
                rf.post('/api/v1/auth/social/yandex/'),
                sociallogin,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_BLOCKED_USER

    def test_save_user_resolves_user_and_saves_sociallogin(
        self,
        monkeypatch,
        rf,
    ):
        """Передает найденного пользователя в SocialLogin и сохраняет связь."""
        resolved_user = UserFactory()
        service = Mock()
        service.resolve_user.return_value = resolved_user

        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-2004',
            email='listener@example.test',
        )
        request = rf.post('/api/v1/auth/social/yandex/')

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
            provider_uid='yandex-2004',
            email='listener@example.test',
            is_email_verified=True,
        )
        sociallogin.save.assert_called_once_with(request)

    def test_save_user_returns_service_domain_error_for_api_request(
        self,
        monkeypatch,
        rf,
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
            uid='yandex-2005',
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
                rf.post('/api/v1/auth/social/yandex/'),
                sociallogin,
            )

        assert exc_info.value.error_code == SOCIAL_AUTH_ERROR_MISSING_EMAIL
        sociallogin.save.assert_not_called()

    def test_save_user_returns_social_save_error_when_link_cannot_be_saved(
        self,
        monkeypatch,
        rf,
    ):
        """Возвращает понятную ошибку, если SocialAccount не сохранился."""
        resolved_user = UserFactory()
        service = Mock()
        service.resolve_user.return_value = resolved_user

        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-2006',
            email='listener@example.test',
            save=Mock(side_effect=IntegrityError),
        )

        monkeypatch.setattr(adapter, 'get_service', lambda: service)
        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        with pytest.raises(SocialAuthException) as exc_info:
            adapter.save_user(
                rf.post('/api/v1/auth/social/yandex/'),
                sociallogin,
            )

        assert (
            exc_info.value.error_code == SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED
        )
