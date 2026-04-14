"""JWT views проекта.

Модуль содержит обертки над стандартными представлениями
`rest_framework_simplejwt`, используемыми для получения
и обновления JWT-токенов.
"""

from rest_framework import status
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
    token_obtain_schema,
    token_refresh_schema,
    token_verify_schema,
)
from users.serializers import CustomTokenObtainPairSerializer


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

    @staticmethod
    def post(request) -> Response:
        """Добавляет refresh token в blacklist."""
        try:
            token = request.data.get('refresh')
            refresh_token = RefreshToken(token)
            refresh_token.blacklist()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)
