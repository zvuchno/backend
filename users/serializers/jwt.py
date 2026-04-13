"""Сериализаторы для аутентификации."""

from rest_framework import serializers


class LogoutSerializer(serializers.Serializer):
    """Сериализатор выхода пользователя."""

    refresh = serializers.CharField(label='Refresh токен')


class TokenPairSerializer(serializers.Serializer):
    """Пара JWT токенов."""

    access = serializers.CharField()
    refresh = serializers.CharField()
