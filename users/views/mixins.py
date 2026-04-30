"""Миксины для представлений пользователей."""

import logging

from django.http import Http404
from rest_framework.exceptions import AuthenticationFailed

from users.constants import SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED
from users.exceptions import SocialAuthException
from users.models import ArtistProfile

logger = logging.getLogger(__name__)


class CurrentArtistProfileMixin:
    """Миксин для получения профиля текущего артиста."""

    select_related = ()
    prefetch_related = ()

    def get_artist_queryset(self):
        queryset = ArtistProfile.objects.all()

        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)

        return queryset

    def get_artist_profile(self):
        try:
            return self.get_artist_queryset().get(user=self.request.user)
        except ArtistProfile.DoesNotExist:
            raise Http404('Профиль артиста не найден.')


class SocialAuthMixin:
    """Миксин для обработки ошибок социальной аутентификации."""

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except (SocialAuthException, AuthenticationFailed) as exc:
            raise exc
        except Exception:
            logger.exception('Внутренняя ошибка social auth.')
            raise AuthenticationFailed({
                'error_code': SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED,
                'detail': 'Не удалось завершить '
                'аутентификацию через провайдера.',
            })
