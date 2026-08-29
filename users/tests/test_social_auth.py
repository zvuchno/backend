"""Тесты социальной аутентификации."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import override_settings
from rest_framework.exceptions import ValidationError

from users.adapters import SocialAccountAdapter
from users.consents_policy import ConsentPolicy, ConsentScenario
from users.constants import (
    SOCIAL_AUTH_ERROR_BLOCKED_USER,
    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
    SOCIAL_AUTH_ERROR_MISSING_EMAIL,
    SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED,
    SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
)
from users.exceptions import SocialAuthException
from users.models import ListenerProfile, UserConsent
from users.services import SocialAuthService
from users.tests.factories import UserFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


YANDEX_PROVIDER = 'yandex'
VK_PROVIDER = 'vk'


def build_sociallogin(
    *,
    provider: str,
    uid: str,
    email: str,
    save: Mock | None = None,
    is_existing: bool = False,
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
        is_existing=is_existing,
        connect=Mock(),
    )
    sociallogin.save = save if save is not None else Mock()

    return sociallogin


class TestSocialAuthService:
    """Тесты обработки пользователя после входа через соцсеть."""

    def test_requires_registration_for_new_social_user(self):
        """Требует явного разрешения на регистрацию нового пользователя."""
        with pytest.raises(SocialAuthException) as exc_info:
            SocialAuthService().resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1001',
                email='new.user@example.test',
                is_email_verified=True,
            )

        assert (
            exc_info.value.error_code
            == SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED
        )
        assert not User.objects.filter(
            email='new.user@example.test',
        ).exists()

    @override_settings(CONSENT_ENFORCE_REQUIRED=True)
    def test_creates_new_passwordless_user_from_trusted_social_email(
        self,
        listener_registration_consents,
    ):
        """Создает нового пользователя после подтверждения регистрации."""
        user = SocialAuthService().resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1001',
            email='  New.User@Example.Test ',
            is_email_verified=True,
            create_account=True,
            accepted_consents=listener_registration_consents,
        )

        assert user.email == 'new.user@example.test'
        assert user.is_email_verified is True
        assert user.has_usable_password() is False
        assert ListenerProfile.objects.filter(
            user=user,
            is_active=True,
        ).exists()

    @override_settings(CONSENT_ENFORCE_REQUIRED=True)
    def test_creates_new_unverified_user_from_untrusted_social_email(
        self,
        listener_registration_consents,
    ):
        """Создает неподтвержденного пользователя от недоверенного provider."""
        user = SocialAuthService().resolve_user(
            provider=VK_PROVIDER,
            provider_uid='vk-1002',
            email='new.user@example.test',
            is_email_verified=False,
            create_account=True,
            accepted_consents=listener_registration_consents,
        )

        assert user.email == 'new.user@example.test'
        assert user.is_email_verified is False
        assert user.has_usable_password() is False

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

    @override_settings(CONSENT_ENFORCE_REQUIRED=True)
    def test_rejects_social_registration_without_required_consents(
        self,
    ):
        """Не создает пользователя без обязательных согласий."""
        with pytest.raises(ValidationError):
            SocialAuthService().resolve_user(
                provider=YANDEX_PROVIDER,
                provider_uid='yandex-1010',
                email='new.user@example.test',
                is_email_verified=True,
                create_account=True,
                accepted_consents=(),
            )

        assert not User.objects.filter(
            email='new.user@example.test',
        ).exists()

    @override_settings(CONSENT_ENFORCE_REQUIRED=True)
    def test_social_registration_saves_consents(
        self,
        listener_registration_consents,
    ):
        """Сохраняет согласия при регистрации через соцсеть."""
        user = SocialAuthService().resolve_user(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-1011',
            email='new.user@example.test',
            is_email_verified=True,
            create_account=True,
            accepted_consents=listener_registration_consents,
        )

        saved_types = set(
            UserConsent.objects.filter(user=user).values_list(
                'document__document_type',
                flat=True,
            ),
        )

        assert saved_types == set(listener_registration_consents)


class TestSocialAccountAdapter:
    """Тесты custom adapter-а социальной аутентификации."""

    def test_pre_social_login_confirms_existing_user_email(
        self,
        monkeypatch,
        rf,
    ):
        """Подтверждает email и привязывает соцсеть к существующему user."""
        user = UserFactory(
            email='listener@example.test',
            is_email_verified=False,
        )
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-2001',
            email=user.email,
        )
        adapter = SocialAccountAdapter()
        request = rf.post('/api/v1/auth/social/yandex/')

        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        adapter.pre_social_login(request, sociallogin)

        user.refresh_from_db()

        assert user.is_email_verified is True
        sociallogin.connect.assert_called_once_with(request, user)

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
            create_account=False,
            accepted_consents=(),
            ip_address='127.0.0.1',
            user_agent='',
        )
        sociallogin.save.assert_called_once_with(request)

    def test_save_user_passes_registration_data_to_service(
        self,
        monkeypatch,
        rf,
    ):
        """Передает параметры регистрации и согласия в social auth service."""
        resolved_user = UserFactory()
        service = Mock()
        service.resolve_user.return_value = resolved_user

        adapter = SocialAccountAdapter()
        sociallogin = build_sociallogin(
            provider=YANDEX_PROVIDER,
            uid='yandex-2007',
            email='listener@example.test',
        )

        consents = set(
            ConsentPolicy.get_required(
                ConsentScenario.LISTENER_REGISTRATION,
            ),
        )

        request = rf.post('/api/v1/auth/social/yandex/')
        request.social_create_account = True
        request.social_consents = consents

        monkeypatch.setattr(adapter, 'get_service', lambda: service)
        monkeypatch.setattr(
            adapter,
            'is_email_verified',
            lambda *args, **kwargs: True,
        )

        adapter.save_user(request, sociallogin)

        service.resolve_user.assert_called_once_with(
            provider=YANDEX_PROVIDER,
            provider_uid='yandex-2007',
            email='listener@example.test',
            is_email_verified=True,
            create_account=True,
            accepted_consents=consents,
            ip_address='127.0.0.1',
            user_agent='',
        )

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
