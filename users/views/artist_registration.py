"""Представление для регистрации артиста.

Модуль содержит endpoint, который отвечает за создание
пользователя и связанного с ним профиля артиста.
"""

from rest_framework.permissions import AllowAny

from users.serializers import ArtistRegistrationSerializer
from .base_registration import BaseRegistrationView


class ArtistRegistrationView(BaseRegistrationView):
    """Представление для регистрации артиста."""

    serializer_class = ArtistRegistrationSerializer
    permission_classes = [AllowAny]
