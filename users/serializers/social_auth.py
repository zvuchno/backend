"""Сериализаторы аутентификации через сторонние сервисы."""

from rest_framework import serializers


class SocialAuthInputSerializer(serializers.Serializer):
    """Сериализатор принимает code и token от провайдера."""

    code = serializers.CharField(
        required=False,
        help_text='Code от провайдера.',
    )
    access_token = serializers.CharField(
        required=False,
        help_text='Access token от провайдера.',
    )
