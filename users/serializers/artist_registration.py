"""Сериализаторы регистрации артиста.

Модуль содержит сериализатор, который отвечает
за создание пользователя и связанного профиля артиста,
а также за формирование ответа с данными профиля.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .base_registration import BaseRegistrationSerializer
from users.models import ArtistProfile

User = get_user_model()


class ArtistRegistrationSerializer(BaseRegistrationSerializer):
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
        сериализатора, затем создает связанный профиль артиста
        с переданным именем. Операция выполняется атомарно.
        """
        name = validated_data.pop('name', None)
        user = super().create(validated_data)
        ArtistProfile.objects.create(
            owner=user,
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
        fields = ('id', 'username', 'email', 'name', 'password')
