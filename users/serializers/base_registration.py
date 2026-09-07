"""Базовые сериализаторы регистрации пользователей."""

from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from users.models import ConsentDocument
from users.serializers.mixins import SafePhoneNumberField
from users.services import ConsentService


class BaseRegistrationSerializer(UserCreateSerializer):
    """Базовый сериализатор регистрации пользователя.

    Расширяет сериализатор создания пользователя из djoser
    и поддерживает обработку дополнительного поля, которое
    используется при создании связанного профиля роли.
    """

    phone = SafePhoneNumberField(
        label='Номер телефона',
        required=True,
    )
    consents = serializers.ListField(
        child=serializers.ChoiceField(
            choices=ConsentDocument.DocumentType.choices,
        ),
        required=False,
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

        scenario = self.get_consent_scenario(attrs)
        accepted_types = set(attrs.get('consents') or ())

        ConsentService.validate(
            scenario=scenario,
            accepted_types=accepted_types,
        )

        return attrs

    def get_consent_scenario(self, attrs):
        """Возвращает сценарий согласий для регистрации."""
        raise NotImplementedError
