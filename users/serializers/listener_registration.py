"""Сериализаторы регистрации слушателя."""

from django.contrib.auth import get_user_model
from django.db import transaction
from phonenumber_field.validators import validate_international_phonenumber
from rest_framework import serializers

from .base_registration import BaseRegistrationSerializer
from users.models import ListenerProfile

User = get_user_model()


class ListenerRegistrationSerializer(BaseRegistrationSerializer):
    """Сериализатор регистрации слушателя.

    Создает пользователя, а затем связанный с ним профиль слушателя.
    Дополнительно принимает номер телефона, проверяет его
    и возвращает в ответе после успешной регистрации.
    """

    extra_field_name = 'phone'
    phone = serializers.CharField(
        label='Номер телефона',
        required=True,
        write_only=True,
    )

    @staticmethod
    def validate_phone(value) -> str:
        """Проверяет корректность и уникальность номера телефона.

        Проводит валидацию номера телефона в международном формате
        и дополнительно проверяет, что такой номер еще не используется
        в профиле другого слушателя.
        """
        if not value:
            return value
        try:
            validate_international_phonenumber(value)
        except Exception:
            raise serializers.ValidationError(
                'Введите номер в международном формате.',
            )
        if ListenerProfile.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                'Слушатель с таким номером уже существует.',
            )
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Создает пользователя и профиль слушателя.

        Сначала создает объект пользователя средствами базового
        сериализатора, затем создает связанный профиль слушателя
        с переданным номером телефона. Операция выполняется атомарно.
        """
        phone = validated_data.pop('phone', None)
        user = super().create(validated_data)
        ListenerProfile.objects.create(
            user=user,
            phone=phone,
        )
        return user

    def to_representation(self, instance):
        """Добавляет номер телефона в данные ответа.

        Формирует стандартное представление пользователя
        и дополняет его данными из связанного профиля слушателя.
        """
        data = super().to_representation(instance)
        listener_profile = getattr(instance, 'listener_profile', None)
        phone = getattr(listener_profile, 'phone', None)
        data['phone'] = str(phone) if phone else None
        return data

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone', 'password')
