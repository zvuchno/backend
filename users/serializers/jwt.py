"""Сериализаторы для аутентификации."""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from users.helpers import run_actions_after_authentication


class LogoutSerializer(serializers.Serializer):
    """Сериализатор выхода пользователя."""

    refresh = serializers.CharField(label='Refresh токен')


class TokenPairSerializer(serializers.Serializer):
    """Пара JWT токенов."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Переопределенный сериализатор выпуска токенов."""

    def validate(self, attrs):
        attrs = super().validate(attrs)

        run_actions_after_authentication(self.user, self.context['request'])

        return attrs
