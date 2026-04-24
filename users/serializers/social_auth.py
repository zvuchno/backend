"""Сериализаторы аутентификации через сторонние сервисы."""

from dj_rest_auth.registration.serializers import SocialLoginSerializer
from rest_framework import serializers


class SocialAuthInputSerializer(SocialLoginSerializer):
    """Сериализатор принимает code / token от провайдера."""

    code = serializers.CharField(
        required=False,
        help_text='Рекомендуемый способ. Код для обмена на бэкенде.',
    )
    access_token = serializers.CharField(
        required=False,
        help_text='Альтернативный способ. Готовый токен доступа провайдера.',
    )
    id_token = serializers.HiddenField(default='')

    def validate(self, attrs):
        """Передано хотя бы одно поле."""
        if not attrs.get('code') and not attrs.get('access_token'):
            raise serializers.ValidationError(
                'Необходимо предоставить code или access_token.',
            )
        attrs = super().validate(attrs)
        if not attrs.get('user'):
            raise serializers.ValidationError(
                'Не удалось получить пользователя от провайдера.',
            )
        return attrs
