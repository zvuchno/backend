"""Миксины для сериализаторов пользователей."""

from django.contrib.auth import get_user_model
from phonenumber_field.validators import validate_international_phonenumber
from rest_framework import serializers

User = get_user_model()


class PhoneRegistrationMixin:
    """Миксин для поля и валидации номера телефона."""

    phone = serializers.CharField(
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
        if not value:
            return value
        try:
            validate_international_phonenumber(value)
        except Exception:
            raise serializers.ValidationError(
                'Введите номер в международном формате.',
            )
        queryset = User.objects.filter(phone=value)
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
        return value
