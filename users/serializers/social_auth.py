"""Сериализаторы для аутентицификации через сторонние сервисы."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class SocialVkLoginSerializer(serializers.Serializer):
    """Сериализатор аутентификации через ВК."""

    code = serializers.CharField(write_only=True)
    redirect_uri = serializers.URLField(write_only=True)


class SocialCompleteSignupSerializer(serializers.Serializer):
    """Сериализатор завершения регистрации, если не передан Email."""

    email = serializers.EmailField(write_only=True)
    signup_token = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                'Пользователь с таким email уже существует.',
            )
        return value
