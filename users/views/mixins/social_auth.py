import logging

from rest_framework.exceptions import AuthenticationFailed

from users.constants import SOCIAL_AUTH_ERROR_OAUTH_AUTH_FAILED
from users.exceptions import SocialAuthException

logger = logging.getLogger(__name__)


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
