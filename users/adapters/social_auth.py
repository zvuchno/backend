"""Адаптеры для интеграции входа с соцсетями."""

import logging
from urllib.parse import urlencode

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from config import settings
from users.constants import (
    MAX_USER_CREATE_ATTEMPTS,
    SOCIAL_AUTH_ERRORS,
    SOCIAL_AUTH_ERROR_BLOCKED_USER,
    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
    SOCIAL_AUTH_ERROR_MISSING_EMAIL,
    SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED,
    SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
    SOCIAL_AUTH_ERROR_USERNAME_GENERATION_FAILED,
)
from users.exceptions import SocialAuthException
from users.helpers import (
    ensure_listener_profile,
    generate_username,
    normalize_email,
    set_unusable_password,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Адаптер регистрации и аутентификации через соцсеть."""

    @staticmethod
    def _ensure_user_is_active(user) -> None:
        """Проверить, что пользователь не заблокирован."""
        if user is None:
            return
        if not user.is_active:
            logger.warning(
                'Попытка заблокированного аккаунта: user_id=%s email=%s',
                user.pk,
                user.email,
            )
            raise SocialAuthException(
                SOCIAL_AUTH_ERROR_BLOCKED_USER,
                SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_BLOCKED_USER],
            )

    def pre_social_login(self, request, sociallogin):
        """Вызывается сразу после аутентификации у провайдера."""
        provider = sociallogin.account.provider
        uid = sociallogin.account.uid
        user = self._find_user_by_social_account(
            provider=provider,
            provider_uid=uid,
        )
        try:
            self._ensure_user_is_active(user)
        except SocialAuthException as exc:
            raise ImmediateHttpResponse(
                self._frontend_error_redirect(exc.error_code, provider),
            )

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        """Создает или находит пользователя после входа через соцсеть."""
        provider = sociallogin.account.provider
        uid = sociallogin.account.uid
        email = sociallogin.user.email
        provider_obj = sociallogin.account.get_provider()
        is_email_verified = self.is_email_verified(provider_obj, email)

        try:
            user = self._login_with_social_data(
                provider=provider,
                provider_uid=uid,
                email=email,
                is_email_verified=is_email_verified,
            )
        except SocialAuthException as exc:
            logger.warning(
                'Social auth failed: provider=%s code=%s',
                provider,
                exc.error_code,
            )
            raise ImmediateHttpResponse(
                self._frontend_error_redirect(exc.error_code, provider),
            )

        sociallogin.user = user
        try:
            sociallogin.save(request)
        except IntegrityError:
            logger.exception(
                'Не удалось сохранить соц аккаунт: '
                'provider=%s uid=%s user_id=%s',
                provider,
                uid,
                user.pk,
            )
            raise ImmediateHttpResponse(
                self._frontend_error_redirect(
                    SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
                    provider,
                ),
            )
        return user

    @staticmethod
    def _find_user_by_social_account(
        *,
        provider: str,
        provider_uid: str,
    ) -> User | None:
        """Ищет пользователя по привязанному social account."""
        social_account = (
            SocialAccount.objects
            .select_related('user')
            .filter(provider=provider, uid=str(provider_uid))
            .first()
        )
        return social_account.user if social_account else None

    def _create_account_from_social(
        self,
        *,
        email: str,
        is_email_verified: bool,
    ) -> User:
        """Создает пользователя из соцсети с retry при конфликте username."""
        for attempt in range(MAX_USER_CREATE_ATTEMPTS):
            try:
                with transaction.atomic():
                    user = User.objects.create(
                        email=email,
                        username=generate_username(email, attempt),
                        is_email_verified=is_email_verified,
                    )
                    set_unusable_password(user)
                    ensure_listener_profile(user)
                    return user

            except IntegrityError:
                existing_user = User.objects.filter(email=email).first()
                if existing_user:
                    self._ensure_user_is_active(existing_user)
                    ensure_listener_profile(existing_user)
                    if not existing_user.is_email_verified:
                        raise SocialAuthException(
                            SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
                            SOCIAL_AUTH_ERRORS[
                                SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED
                            ],
                        )
                    return existing_user
                continue
        raise SocialAuthException(
            SOCIAL_AUTH_ERROR_USERNAME_GENERATION_FAILED,
            SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_USERNAME_GENERATION_FAILED],
        )

    def _login_with_social_data(
        self,
        *,
        provider: str,
        provider_uid: str,
        email: str,
        is_email_verified: bool,
    ) -> User:
        """Обрабатывает вход через соцсеть."""
        user = self._find_user_by_social_account(
            provider=provider,
            provider_uid=provider_uid,
        )
        if user:
            self._ensure_user_is_active(user)
            ensure_listener_profile(user)
            return user

        if not email:
            raise SocialAuthException(
                SOCIAL_AUTH_ERROR_MISSING_EMAIL,
                SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_MISSING_EMAIL],
            )

        email = normalize_email(email)

        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            self._ensure_user_is_active(existing_user)
            ensure_listener_profile(existing_user)
            if not existing_user.is_email_verified:
                raise SocialAuthException(
                    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
                    SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED],
                )
            return existing_user

        return self._create_account_from_social(
            email=email,
            is_email_verified=is_email_verified,
        )

    def on_authentication_error(
        self,
        request,
        provider_id,
        error=None,
        exception=None,
        extra_context=None,
    ):
        """Редирект на фронт в случае ошибки."""
        logger.warning(
            'OAuth provider auth error: provider=%s error=%s exception=%s',
            provider_id,
            error,
            exception,
        )
        raise ImmediateHttpResponse(
            self._frontend_error_redirect(
                SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED,
                provider_id,
            ),
        )

    @staticmethod
    def _frontend_error_redirect(
        error_code: str,
        provider: str = 'unknown',
    ) -> HttpResponseRedirect:
        """Вспомогательный метод для редиректа на фронт с ошибкой."""
        base_url = getattr(settings, 'FRONTEND_SOCIAL_AUTH_URL', '/')
        params = urlencode({
            'status': 'error',
            'error_code': error_code,
            'provider': provider,
        })
        return redirect(f'{base_url}?{params}')
