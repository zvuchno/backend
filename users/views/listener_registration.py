"""Представление для регистрации слушателя.

Модуль содержит endpoint, который отвечает за создание
пользователя и связанного с ним профиля слушателя.
"""

from rest_framework.permissions import AllowAny

from users.serializers import ListenerRegistrationSerializer
from .base_registration import BaseRegistrationView


class ListenerRegistrationView(BaseRegistrationView):
    """Представление для регистрации слушателя."""

    serializer_class = ListenerRegistrationSerializer
    permission_classes = [AllowAny]
