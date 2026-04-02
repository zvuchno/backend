"""Сериализаторы для аутентицификации через сторонние сервисы."""

from rest_framework import serializers


class SocialVkLoginSerializer(serializers.Serializer):
    """Сериализатор атуентификации через ВК."""

    code = serializers.CharField(write_only=True)
    redirect_uri = serializers.URLField(write_only=True)


class SocialCompleteRegistrationSerializer(serializers.Serializer):
    """Сериализатор завершения регистрации, если не передан Email."""

    email = serializers.EmailField(write_only=True)
    signup_token = serializers.CharField(write_only=True)
