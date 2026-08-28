"""Базовые сериализаторы регистрации пользователей."""

from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from users.models import ConsentDocument
from users.services import ConsentService


class BaseRegistrationSerializer(UserCreateSerializer):
    """Базовый сериализатор регистрации пользователя.

    Расширяет сериализатор создания пользователя из djoser
    и поддерживает обработку дополнительного поля, которое
    используется при создании связанного профиля роли.
    """

    phone = serializers.CharField(required=True, allow_blank=False)
    consents = serializers.ListField(
        child=serializers.ChoiceField(
            choices=ConsentDocument.DocumentType.choices,
        ),
        allow_empty=False,
        write_only=True,
    )

    extra_fields_names = ('consents',)

    def validate(self, attrs):
        """Подготавливает данные перед общей валидацией.

        Дополнительные поля, которые не входят в модель пользователя,
        временно исключаются перед вызовом родительской валидации,
        а затем возвращаются обратно.
        """
        skipped_fields = {}

        for extra_field_name in self.extra_fields_names:
            skipped_fields[extra_field_name] = attrs.pop(
                extra_field_name,
                None,
            )
        attrs = super().validate(attrs)
        attrs.update(skipped_fields)

        context = self.get_consent_context(attrs)
        accepted_types = set(attrs.get('consents') or ())

        ConsentService.validate(
            context=context,
            accepted_types=accepted_types,
        )

        return attrs

    def get_consent_context(self, attrs):
        """Возвращает контекст согласий для регистрации."""
        raise NotImplementedError
