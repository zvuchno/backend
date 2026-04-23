"""Адаптеры для интеграции входа с соцсетями."""

import logging
from urllib.parse import urlencode

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from config import settings
from users.constants import (
    SOCIAL_AUTH_ERRORS,
    SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED,
    SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
)
from users.exceptions import SocialAuthException
from users.services import SocialAuthService

logger = logging.getLogger(__name__)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Адаптер регистрации и аутентификации через соцсеть."""

    service_class = SocialAuthService

    def get_service(self):
        """Возвращает объект обработчика social auth."""
        return self.service_class()

    def pre_social_login(self, request, sociallogin):
        """Вызывается сразу после аутентификации у провайдера."""
        provider = sociallogin.account.provider
        uid = sociallogin.account.uid
        service = self.get_service()
        user = service.find_user_by_social_account(
            provider=provider,
            provider_uid=uid,
        )
        try:
            service.ensure_user_is_active(user)
        except SocialAuthException as exc:
            raise ImmediateHttpResponse(
                self._handle_auth_error(
                    request,
                    exc.error_code,
                    provider,
                ),
            )

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        """Создает или находит пользователя после входа через соцсеть."""
        provider = sociallogin.account.provider
        uid = sociallogin.account.uid
        email = sociallogin.user.email
        provider_obj = sociallogin.account.get_provider()
        is_email_verified = self.is_email_verified(provider_obj, email)
        service = self.get_service()
        try:
            user = service.resolve_user(
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
                self._handle_auth_error(
                    request,
                    exc.error_code,
                    provider,
                ),
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
                self._handle_auth_error(
                    request,
                    SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
                    provider,
                ),
            )
        return user

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
            self._handle_auth_error(
                request,
                SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED,
                provider_id,
            ),
        )

    def _frontend_error_redirect(
        self,
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

    def _is_api_request(self, request) -> bool:
        """Проверяет, что запрос относится к API social auth."""
        return request.path.startswith('/api/')

    def _handle_auth_error(
        self,
        request,
        error_code: str,
        provider: str = 'unknown',
    ) -> HttpResponseRedirect:
        """Отдает ошибку в формате, подходящем для текущего flow."""
        if self._is_api_request(request):
            raise SocialAuthException(
                error_code,
                SOCIAL_AUTH_ERRORS.get(error_code, 'Ошибка аутентификации.'),
            )

        raise ImmediateHttpResponse(
            self._frontend_error_redirect(error_code, provider),
        )
