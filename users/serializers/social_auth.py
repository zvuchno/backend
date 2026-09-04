"""Сериализаторы аутентификации через сторонние сервисы."""

import logging

from dj_rest_auth.registration.serializers import SocialLoginSerializer
from rest_framework import serializers

from users.models import ConsentDocument

logger = logging.getLogger(__name__)


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

    create_account = serializers.BooleanField(
        required=False,
        default=False,
        help_text='Разрешает создать аккаунт, '
        'если пользователь ещё не существует.',
    )
    consents = serializers.ListField(
        child=serializers.ChoiceField(
            choices=ConsentDocument.DocumentType.choices,
        ),
        required=False,
        default=list,
        write_only=True,
        label='Принятые согласия',
    )

    def validate(self, attrs):
        """Передано хотя бы одно поле."""
        if not attrs.get('code') and not attrs.get('access_token'):
            raise serializers.ValidationError(
                'Необходимо предоставить code или access_token.',
            )

        create_account = attrs.pop('create_account', False)
        consents = attrs.pop('consents', [])

        request = self.context['request']
        request.social_create_account = create_account
        request.social_consents = set(consents)

        logger.warning(
            'SOCIAL serializer request=%s create_account=%r consents=%r',
            id(request),
            create_account,
            consents,
        )

        attrs = super().validate(attrs)
        if not attrs.get('user'):
            raise serializers.ValidationError(
                'Не удалось получить пользователя от провайдера.',
            )
        return attrs
