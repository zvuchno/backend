"""Базовые представления для регистрации пользователей."""

from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny


class BaseRegistrationView(CreateAPIView):
    """Базовое представление для регистрации пользователя.

    Предоставляет общую конфигурацию для ручек регистрации
    и используется как родительский класс для представлений
    регистрации слушателя и артиста.
    """

    permission_classes = [AllowAny]
