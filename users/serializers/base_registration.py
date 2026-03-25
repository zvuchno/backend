"""Базовые сериализаторы регистрации пользователей."""

from djoser.serializers import UserCreateSerializer
from rest_framework import serializers


class BaseRegistrationSerializer(UserCreateSerializer):
    """Базовый сериализатор регистрации пользователя.

    Расширяет сериализатор создания пользователя из djoser
    и поддерживает обработку дополнительного поля, которое
    используется при создании связанного профиля роли.
    """

    phone = serializers.CharField(required=True, allow_blank=False)
    extra_field_name = None

    def validate(self, attrs):
        """Подготавливает данные перед общей валидацией.

        Если в сериализаторе задано дополнительное поле,
        которое не входит в модель пользователя, оно временно
        исключается из данных перед вызовом родительской валидации,
        а затем возвращается обратно.
        """
        extra_field_value = None
        if self.extra_field_name:
            extra_field_value = attrs.pop(self.extra_field_name, None)
        attrs = super().validate(attrs)
        if self.extra_field_name:
            attrs[self.extra_field_name] = extra_field_value
        return attrs
