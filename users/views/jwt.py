"""JWT views проекта.

Модуль содержит обертки над стандартными представлениями
`rest_framework_simplejwt`, используемыми для получения
и обновления JWT-токенов.
"""

from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.vk.views import VKOAuth2Adapter
from allauth.socialaccount.providers.yandex.views import YandexOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from users.schemas import (
    logout_schema,
    social_auth_schema,
    token_obtain_schema,
    token_refresh_schema,
    token_verify_schema,
)
from users.serializers import (
    CustomTokenObtainPairSerializer,
    SocialAuthInputSerializer,
)
from users.views.mixins import SocialAuthMixin


@token_obtain_schema
class CustomTokenObtainPairView(TokenObtainPairView):
    """Выдача пары JWT токенов (access + refresh).

    Обертка над стандартным TokenObtainPairView из Simple JWT.

    Класс используется для возможности настройки политик DRF
    (throttling, permissions и т.п.), не изменяя стандартную
    логику выдачи токенов.

    Эндпоинт:
        POST /auth/token/create/
    """

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


@token_refresh_schema
class CustomTokenRefreshView(TokenRefreshView):
    """Обновление access токена по refresh токену.

    Обертка над стандартным TokenRefreshView из Simple JWT.

    Класс используется для возможности настройки политик DRF
    (throttling и др.) без изменения стандартного поведения
    Simple JWT.

    Эндпоинт:
        POST /auth/token/refresh/
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'refresh'


@token_verify_schema
class CustomTokenVerifyView(TokenVerifyView):
    """Верификация access токена.

    Обертка над стандартным TokenVerifyView из Simple JWT.

    Класс используется для возможности настройки политик DRF
    (throttling и др.) без изменения стандартного поведения
    Simple JWT.

    Эндпоинт:
        POST /auth/token/verify/
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verify'


@logout_schema
class CustomLogoutView(APIView):
    """Инвалидирует refresh токен пользователя."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'logout'

    @staticmethod
    def post(request) -> Response:
        """Добавляет refresh token в blacklist."""
        token = request.data.get('refresh')
        if not token:
            raise ValidationError(
                {'refresh': 'Токен не предоставлен.'},
            )
        try:
            refresh_token = RefreshToken(token)
            refresh_token.blacklist()
        except Exception:
            raise ValidationError(
                {'refresh': 'Некорректный refresh токен.'},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


@social_auth_schema
class VKLogin(SocialAuthMixin, SocialLoginView):
    """Аутентификация через ВК."""

    adapter_class = VKOAuth2Adapter
    serializer_class = SocialAuthInputSerializer
    client_class = OAuth2Client
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'social_auth'


@social_auth_schema
class YandexLogin(SocialAuthMixin, SocialLoginView):
    """Аутентификация через Яндекс."""

    adapter_class = YandexOAuth2Adapter
    serializer_class = SocialAuthInputSerializer
    client_class = OAuth2Client
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'social_auth'
