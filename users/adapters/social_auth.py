"""Адаптеры для интеграции входа с соцсетями."""

import logging

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.yandex.views import (
    YandexOAuth2Adapter as AllauthYandexOAuth2Adapter,
)
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from requests import HTTPError

from common.utils import get_client_ip, get_user_agent
from common.utils.urls import build_frontend_url

from users.constants import (
    SOCIAL_AUTH_ERRORS,
    SOCIAL_AUTH_ERROR_EMAIL_CONFLICT,
    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
    SOCIAL_AUTH_ERROR_MISSING_EMAIL,
    SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED,
    SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED,
    SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
)
from users.exceptions import SocialAuthException
from users.services import SocialAuthService

logger = logging.getLogger(__name__)


class YandexOAuth2Adapter(AllauthYandexOAuth2Adapter):
    """Проверяет, что токен Яндекса выпущен для нашего OAuth-приложения."""

    def complete_login(self, request, app, token, **kwargs):
        """Отклоняет access token другого OAuth-приложения."""
        login = super().complete_login(request, app, token, **kwargs)
        token_client_id = login.account.extra_data.get('client_id')

        if str(token_client_id) != str(app.client_id):
            raise HTTPError('Yandex OAuth client_id mismatch')

        return login


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Адаптер регистрации и аутентификации через соцсеть."""

    service_class = SocialAuthService

    def get_service(self):
        """Возвращает объект обработчика social auth."""
        return self.service_class()

    def is_auto_signup_allowed(self, request, sociallogin) -> bool:
        """Разрешает регистрацию только по явному флагу."""
        create_account = getattr(
            request,
            'social_create_account',
            False,
        )

        if not create_account:
            if self._is_api_request(request):
                raise SocialAuthException(
                    SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED,
                    SOCIAL_AUTH_ERRORS[
                        SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED
                    ],
                )

            return False

        if self._is_api_request(request):
            email = sociallogin.user.email

            if (
                email
                and EmailAddress.objects.filter(
                    email__iexact=email,
                ).exists()
            ):
                raise SocialAuthException(
                    SOCIAL_AUTH_ERROR_EMAIL_CONFLICT,
                    SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_EMAIL_CONFLICT],
                )

        return True

    def pre_social_login(self, request, sociallogin):
        """Обрабатывает пользователя до завершения social login."""
        provider = sociallogin.account.provider
        uid = sociallogin.account.uid
        email = sociallogin.user.email
        provider_obj = sociallogin.account.get_provider()

        service = self.get_service()
        social_account_user = service.find_user_by_social_account(
            provider=provider,
            provider_uid=uid,
        )

        if social_account_user is not None:
            try:
                service.ensure_user_is_active(social_account_user)
                service.mark_email_verified_from_social_provider(
                    user=social_account_user,
                    email=email,
                    is_email_verified=self.is_email_verified(
                        provider_obj,
                        email,
                    ),
                )
                service.accept_registration_consents(
                    user=social_account_user,
                    create_account=getattr(
                        request,
                        'social_create_account',
                        False,
                    ),
                    accepted_consents=getattr(
                        request,
                        'social_consents',
                        (),
                    ),
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request),
                )
            except SocialAuthException as exc:
                self._handle_auth_error(
                    request,
                    exc.error_code,
                    provider,
                )

            return

        if not email:
            self._handle_auth_error(
                request,
                SOCIAL_AUTH_ERROR_MISSING_EMAIL,
                provider,
            )

        email_user = service.find_user_by_email(email)
        if email_user is None:
            return

        try:
            service.ensure_user_is_active(email_user)

            if not email_user.is_email_verified:
                raise SocialAuthException(
                    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
                    SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED],
                )

            service.mark_email_verified_from_social_provider(
                user=email_user,
                email=email,
                is_email_verified=self.is_email_verified(
                    provider_obj,
                    email,
                ),
            )
            service.accept_registration_consents(
                user=email_user,
                create_account=getattr(
                    request,
                    'social_create_account',
                    False,
                ),
                accepted_consents=getattr(
                    request,
                    'social_consents',
                    (),
                ),
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
            )
        except SocialAuthException as exc:
            self._handle_auth_error(
                request,
                exc.error_code,
                provider,
            )

        if not sociallogin.is_existing:
            sociallogin.connect(request, email_user)

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
                create_account=getattr(
                    request,
                    'social_create_account',
                    False,
                ),
                accepted_consents=getattr(
                    request,
                    'social_consents',
                    (),
                ),
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
            )
        except SocialAuthException as exc:
            logger.warning(
                'Social auth failed: provider=%s code=%s',
                provider,
                exc.error_code,
            )
            self._handle_auth_error(
                request,
                exc.error_code,
                provider,
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
            self._handle_auth_error(
                request,
                SOCIAL_AUTH_ERROR_SOCIAL_SAVE_FAILED,
                provider,
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
        self._handle_auth_error(
            request,
            SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED,
            provider_id,
        )

    def _frontend_error_redirect(
        self,
        error_code: str,
        provider: str = 'unknown',
    ) -> HttpResponseRedirect:
        """Вспомогательный метод для редиректа на фронт с ошибкой."""
        return redirect(
            build_frontend_url(
                settings.FRONTEND_SOCIAL_AUTH_PATH,
                {
                    'status': 'error',
                    'error_code': error_code,
                    'provider': provider,
                },
            ),
        )

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
