"""Сериализаторы регистрации артиста."""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from common.utils import get_client_ip, get_user_agent

from ..consents_policy import ConsentScenario
from ..services import ConsentService
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

    extra_fields_names = (
        *BaseRegistrationSerializer.extra_fields_names,
        'name',
        'profile_type',
    )
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
        accepted_types = set(validated_data.pop('consents', ()))

        scenario = (
            ConsentScenario.LABEL_REGISTRATION
            if profile_type == ArtistProfileType.LABEL
            else ConsentScenario.ARTIST_REGISTRATION
        )

        user = super().create(validated_data)
        ListenerProfile.objects.create(user=user)
        ArtistProfile.objects.create(
            user=user,
            name=name,
            profile_type=profile_type,
        )

        request = self.context.get('request')

        ConsentService.accept(
            scenario=scenario,
            accepted_types=accepted_types,
            user=user,
            email=user.email,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
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

    def get_consent_scenario(self, attrs):
        if attrs['profile_type'] == ArtistProfileType.LABEL:
            return ConsentScenario.LABEL_REGISTRATION

        return ConsentScenario.ARTIST_REGISTRATION

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
            'consents',
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
