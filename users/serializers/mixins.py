"""Миксины для сериализаторов пользователей."""

from django.contrib.auth import get_user_model
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

User = get_user_model()


class SafePhoneNumberField(PhoneNumberField):
    """Поле телефона с безопасным перехватом ошибок библиотеки."""

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError:
            raise
        except Exception:
            raise serializers.ValidationError(
                'Введите корректный номер телефона.',
            )


class PhoneRegistrationMixin:
    """Миксин для поля и валидации номера телефона."""

    phone = SafePhoneNumberField(
        label='Номер телефона',
        required=True,
        write_only=True,
    )

    def validate_phone(self, value) -> str:
        """Проверяет корректность и уникальность номера телефона.

        Проводит валидацию номера телефона в международном формате
        и дополнительно проверяет, что такой номер еще не используется
        другим пользователем.
        """
        normalized_value = str(value)
        queryset = User.objects.filter(phone=normalized_value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        else:
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                queryset = queryset.exclude(pk=request.user.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                'Пользователь с таким номером уже существует.',
            )
        return normalized_value
