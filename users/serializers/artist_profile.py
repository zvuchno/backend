"""Сериализаторы профиля артиста."""

from django.db import transaction
from rest_framework import serializers

from users.models import ArtistContact, ArtistProfile, ArtistSocial


class ArtistCoverUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления обложки артиста."""

    class Meta:
        model = ArtistProfile
        fields = ('cover',)


class ArtistContactSerializer(serializers.ModelSerializer):
    """Сериализатор контактных данных артиста."""

    class Meta:
        model = ArtistContact
        fields = ('label', 'value')


class ArtistSocialSerializer(serializers.ModelSerializer):
    """Сериализатор ссылок на соцсети артиста."""

    class Meta:
        model = ArtistSocial
        fields = ('label', 'value')


class ArtistPublicShortSerializer(serializers.ModelSerializer):
    """Сериализатор публичного профиля артиста."""

    class Meta:
        model = ArtistProfile
        fields = (
            'name',
            'description',
            'cover',
            'city',
            'url',
            'slug',
        )


class ArtistPublicSerializer(ArtistPublicShortSerializer):
    """Расширенный сериализатор публичного профиля артиста."""

    contacts = ArtistContactSerializer(many=True, read_only=True)
    socials = ArtistSocialSerializer(many=True, read_only=True)

    class Meta(ArtistPublicShortSerializer.Meta):
        fields = (
            'contacts',
            'socials',
        ) + ArtistPublicShortSerializer.Meta.fields


class ArtistMeSerializer(ArtistPublicSerializer):
    """Сериализатор профиля текущего артиста."""

    username = serializers.ReadOnlyField(
        label='Имя пользователя',
        source='owner.username',
    )
    email = serializers.ReadOnlyField(
        label='Email',
        source='owner.email',
    )

    class Meta(ArtistPublicSerializer.Meta):
        fields = (
            'username',
            'email',
            'name',
            'description',
            'cover',
            'city',
            'url',
            'phone',
            'contacts',
            'socials',
        )


class ArtistMeUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления профиля артиста."""

    contacts = ArtistContactSerializer(many=True, required=False)
    socials = ArtistSocialSerializer(many=True, required=False)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновляет артиста и заменяет связанные контакты и соцсети."""
        contacts_data = validated_data.pop('contacts', None)
        socials_data = validated_data.pop('socials', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if contacts_data is not None:
            instance.contacts.all().delete()
            contacts = [
                ArtistContact(artist=instance, **contact_data)
                for contact_data in contacts_data
            ]
            ArtistContact.objects.bulk_create(contacts)
        if socials_data is not None:
            instance.socials.all().delete()
            socials = [
                ArtistSocial(artist=instance, **social_data)
                for social_data in socials_data
            ]
            ArtistSocial.objects.bulk_create(socials)
        return instance

    class Meta:
        model = ArtistProfile
        fields = (
            'name',
            'description',
            'city',
            'url',
            'phone',
            'socials',
            'contacts',
        )
