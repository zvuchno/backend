from dj_rest_auth.serializers import LoginSerializer
from rest_framework import serializers


class CookieLoginSerializer(LoginSerializer):
    """Сериализатор входа в cookie-сессию."""

    username = None
    email = serializers.EmailField(required=True)


class CookieLoginResponseSerializer(serializers.Serializer):
    """Ответ после успешного входа в cookie-сессию."""

    authenticated = serializers.BooleanField()


class CookieRefreshResponseSerializer(serializers.Serializer):
    """Ответ после обновления cookie-сессии."""

    refreshed = serializers.BooleanField()


class CookieLogoutResponseSerializer(serializers.Serializer):
    """Сериализатор ответа при выходе из JWT-сессии."""

    detail = serializers.CharField()
