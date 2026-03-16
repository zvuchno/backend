"""JWT views проекта.

Модуль содержит обертки над стандартными представлениями
`rest_framework_simplejwt`, используемыми для получения
и обновления JWT-токенов.

Логика Simple JWT не переопределяется — классы добавлены
для возможности настройки политик DRF (например throttling)
без изменения поведения стандартных эндпоинтов.

Используются вместо стандартных:
    TokenObtainPairView
    TokenRefreshView
"""

from drf_spectacular.utils import extend_schema
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


@extend_schema(tags=['Auth'])
class CustomTokenObtainPairView(TokenObtainPairView):
    """Выдача пары JWT токенов (access + refresh).

    Обертка над стандартным TokenObtainPairView из Simple JWT.

    Класс используется для возможности настройки политик DRF
    (throttling, permissions и т.п.), не изменяя стандартную
    логику выдачи токенов.

    Эндпоинт:
        POST /auth/token/create/
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


@extend_schema(tags=['Auth'])
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


@extend_schema(tags=['Auth'])
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


@extend_schema(
    tags=['Auth'],
    auth=[],
)
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
