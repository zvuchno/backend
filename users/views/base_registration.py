"""Базовые представления для регистрации пользователей."""

from dj_rest_auth.jwt_auth import set_jwt_cookies
from django.middleware.csrf import get_token
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from users.helpers import run_actions_after_authentication
from users.services.email_verification import request_email_verification
from users.throttling import RegistrationThrottle


class BaseRegistrationView(CreateAPIView):
    """Базовое представление для регистрации пользователя.

    Предоставляет общую конфигурацию для ручек регистрации
    и используется как родительский класс для представлений
    регистрации слушателя и артиста.
    """

    permission_classes = [AllowAny]
    throttle_classes = [RegistrationThrottle]

    def perform_create(self, serializer):
        """Создает пользователя и отправляет письмо подтверждения email."""
        self.created_user = serializer.save()
        request_email_verification(self.created_user)

    def create(self, request, *args, **kwargs):
        """Создает пользователя и сразу открывает JWT-сессию."""
        response = super().create(request, *args, **kwargs)

        self._set_auth_cookies(
            response=response,
            user=self.created_user,
            request=request,
        )

        return response

    def _set_auth_cookies(self, response, user, request) -> None:
        """Устанавливает JWT-cookie после регистрации."""
        refresh = RefreshToken.for_user(user)

        set_jwt_cookies(
            response,
            refresh.access_token,
            refresh,
        )

        get_token(request)
        run_actions_after_authentication(user, request)
