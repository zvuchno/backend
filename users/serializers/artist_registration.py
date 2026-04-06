"""Сериализаторы регистрации артиста."""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .base_registration import BaseRegistrationSerializer
from .mixins import PhoneRegistrationMixin
from users.models import ArtistProfile, ListenerProfile

User = get_user_model()


class ArtistRegistrationSerializer(
    PhoneRegistrationMixin,
    BaseRegistrationSerializer,
):
    """Сериализатор регистрации артиста.

    Создает пользователя, а затем связанный с ним профиль артиста.
    Дополнительно принимает имя артиста и возвращает его
    в ответе после успешной регистрации.
    """

    extra_field_name = 'name'
    name = serializers.CharField(
        label='Имя артиста',
        required=True,
        write_only=True,
    )

    @transaction.atomic
    def create(self, validated_data):
        """Создает пользователя и профиль артиста.

        Сначала создает объект пользователя средствами базового
        сериализатора, затем создает связанный профиль слушателя и артиста
        с переданным именем. Операция выполняется атомарно.
        """
        name = validated_data.pop('name', None)
        user = super().create(validated_data)
        ListenerProfile.objects.create(user=user)
        ArtistProfile.objects.create(
            user=user,
            name=name,
        )
        return user

    def to_representation(self, instance):
        """Добавляет имя артиста в данные ответа.

        Формирует стандартное представление пользователя
        и дополняет его данными из связанного профиля артиста.
        """
        data = super().to_representation(instance)
        artist_profile = getattr(instance, 'artist_profile', None)
        name = getattr(artist_profile, 'name', None)
        data['name'] = str(name) if name else None
        return data

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone', 'name', 'password')


class BecomeArtistSerializer(serializers.ModelSerializer):
    """Сериализатор для реализации возможности стать артистом слушателю."""

    class Meta:
        model = ArtistProfile
        fields = ('name',)

    def validate(self, attrs):
        user = self.context['request'].user
        if hasattr(user, 'artist_profile'):
            raise serializers.ValidationError(
                {'detail': 'У пользователя уже есть профиль артиста.'},
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Создает профиль артиста, если его нет."""
        artist_profile, _ = ArtistProfile.objects.get_or_create(
            user=self.context['request'].user,
            defaults=validated_data,
        )
        # todo после PR 117
        # ensure_listener_profile(user)
        return artist_profile
