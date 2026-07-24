"""Сериализаторы регистрации артиста."""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .base_registration import BaseRegistrationSerializer
from .mixins import PhoneRegistrationMixin
from users.models import ArtistProfile, ArtistProfileType, ListenerProfile

User = get_user_model()


class ArtistRegistrationSerializer(
    PhoneRegistrationMixin,
    BaseRegistrationSerializer,
):
    """Сериализатор регистрации артиста или лейбла.

    Создает пользователя, а затем связанный с ним профиль артиста
    или лейбла.
    """

    extra_fields_names = ['name', 'profile_type']
    name = serializers.CharField(
        label='Имя артиста / название лейбла',
        required=True,
        write_only=True,
    )
    profile_type = serializers.ChoiceField(
        choices=ArtistProfileType.choices,
        default=ArtistProfileType.ARTIST,
        write_only=True,
    )

    @transaction.atomic
    def create(self, validated_data):
        """Создает пользователя и профиль артиста или лейбла.

        Сначала создает объект пользователя средствами базового
        сериализатора, затем создает связанный профиль слушателя и артиста
        с переданным именем. Операция выполняется атомарно.
        """
        name = validated_data.pop('name')
        profile_type = validated_data.pop('profile_type')

        user = super().create(validated_data)
        ListenerProfile.objects.create(user=user)
        ArtistProfile.objects.create(
            user=user,
            name=name,
            profile_type=profile_type,
        )
        return user

    def to_representation(self, instance):
        """Добавляет имя артиста в данные ответа.

        Формирует стандартное представление пользователя
        и дополняет его данными из связанного профиля артиста.
        """
        data = super().to_representation(instance)
        artist_profile = getattr(instance, 'artist_profile', None)
        data['name'] = (
            artist_profile.name
            if artist_profile and artist_profile.name
            else None
        )
        data['profile_type'] = (
            artist_profile.profile_type if artist_profile else None
        )
        return data

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'phone',
            'name',
            'profile_type',
            'password',
        )


class ArtistRegistrationResponseSerializer(serializers.ModelSerializer):
    """Сериализатор ответа регистрации артиста или лейбла."""

    name = serializers.CharField()
    profile_type = serializers.ChoiceField(
        choices=ArtistProfileType.choices,
    )

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'phone',
            'name',
            'profile_type',
        )
