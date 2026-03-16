"""Представление для регистрации слушателя.

Модуль содержит endpoint, который отвечает за создание
пользователя и связанного с ним профиля слушателя.
"""

from rest_framework.permissions import AllowAny

from .base_registration import BaseRegistrationView
from users.serializers import ListenerRegistrationSerializer


class ListenerRegistrationView(BaseRegistrationView):
    """Представление для регистрации слушателя."""

    serializer_class = ListenerRegistrationSerializer
    permission_classes = [AllowAny]
