"""Базовые представления для регистрации пользователей."""

from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle

from users.services.email_verification import request_email_verification


class BaseRegistrationView(CreateAPIView):
    """Базовое представление для регистрации пользователя.

    Предоставляет общую конфигурацию для ручек регистрации
    и используется как родительский класс для представлений
    регистрации слушателя и артиста.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'registration'

    def perform_create(self, serializer):
        """Создает пользователя и отправляет письмо подтверждения email."""
        user = serializer.save()
        request_email_verification(user)
