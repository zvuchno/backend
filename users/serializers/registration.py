from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from djoser.serializers import UserCreateSerializer
from phonenumber_field.validators import validate_international_phonenumber
from rest_framework import serializers

from users.models import ListenerProfile

User = get_user_model()


class ListenerRegistrationSerializer(UserCreateSerializer):
    """Расширенный сериализатор для слушателя."""
    phone = serializers.CharField(
        label='Номер телефона',
        required=False,
    )

    @staticmethod
    def validate_phone(value):
        """Валидация телефона и перехват ошибки."""
        if not value:
            return value
        try:
            validate_international_phonenumber(value)
        except Exception:
            raise serializers.ValidationError(
                'Введите номер в международном формате.'
            )
        return value

    def validate(self, attrs):
        phone = attrs.pop('phone', None)
        attrs = super().validate(attrs)
        attrs['phone'] = phone
        return attrs

    def create(self, validated_data):
        """Метод для сохранения профиля слушателя."""
        phone = self.validated_data.pop('phone', None)
        user = super().create(self.validated_data)
        ListenerProfile.objects.create(
            user=user,
            phone=phone,
        )
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        listener_profile = getattr(instance, 'listener_profile', None)
        phone = getattr(listener_profile, 'phone', None)
        data['phone'] = str(phone) if phone else None
        return data

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('id', 'username', 'email', 'phone', 'password')


class ArtistRegistrationSerializer(UserCreateSerializer):
    """Расширенный сериализатор для слушателя."""
    phone = serializers.CharField(
        label='Номер телефона',
        required=False,
    )

    @staticmethod
    def validate_phone(value):
        """Валидация телефона и перехват ошибки."""
        if not value:
            return value
        try:
            validate_international_phonenumber(value)
        except Exception:
            raise serializers.ValidationError(
                'Введите номер в международном формате.'
            )
        return value

    def validate(self, attrs):
        phone = attrs.pop('phone', None)
        attrs = super().validate(attrs)
        attrs['phone'] = phone
        return attrs

    def create(self, validated_data):
        """Метод для сохранения профиля слушателя."""
        phone = self.validated_data.pop('phone', None)
        user = super().create(self.validated_data)
        ListenerProfile.objects.create(
            user=user,
            phone=phone,
        )
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        listener_profile = getattr(instance, 'listener_profile', None)
        phone = getattr(listener_profile, 'phone', None)
        data['phone'] = str(phone) if phone else None
        return data

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('id', 'username', 'email', 'phone', 'password')
