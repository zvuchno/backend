"""Сериализаторы профиля артиста."""

from django.db import IntegrityError, transaction
from rest_framework import serializers

from users.models import ArtistContact, ArtistProfile, ArtistSocial
from users.services import ensure_listener_profile


class ArtistCoverUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления обложки артиста."""

    class Meta:
        model = ArtistProfile
        fields = ('cover',)


class ArtistContactSerializer(serializers.ModelSerializer):
    """Сериализатор контактных данных артиста."""

    id = serializers.IntegerField(required=False)

    class Meta:
        model = ArtistContact
        fields = ('id', 'label', 'value')


class ArtistSocialSerializer(serializers.ModelSerializer):
    """Сериализатор ссылок на соцсети артиста."""

    id = serializers.IntegerField(required=False)

    class Meta:
        model = ArtistSocial
        fields = ('id', 'label', 'value')


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

    class Meta(ArtistPublicSerializer.Meta):
        fields = ArtistPublicSerializer.Meta.fields


class ArtistMeUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления профиля артиста."""

    contacts = ArtistContactSerializer(many=True, required=False)
    socials = ArtistSocialSerializer(many=True, required=False)

    @staticmethod
    def _sync_nested_items(instance, items_data, model, related_name) -> None:
        """Синхронизирует состав связанных объектов по id.

        Новые создает, отсутствующие в запросе удаляет.
        """
        manager = getattr(instance, related_name)
        existing_items = {item.id: item for item in manager.all()}
        received_ids = set()
        new_items = []
        items_to_update = []

        for item_data in items_data:
            item_id = item_data.get('id')
            if item_id is None:
                new_items.append(model(artist=instance, **item_data))
                continue

            item = existing_items.get(item_id)
            if item is None:
                raise serializers.ValidationError({
                    related_name: (
                        f'Запись с id={item_id} не найдена '
                        'или не принадлежит артисту.'
                    ),
                })
            for attr, value in item_data.items():
                if attr != 'id':
                    setattr(item, attr, value)
            items_to_update.append(item)
            received_ids.add(item_id)
        if new_items:
            model.objects.bulk_create(new_items)
        if items_to_update:
            model.objects.bulk_update(items_to_update, ['label', 'value'])

        ids_for_delete = set(existing_items.keys()) - received_ids
        if ids_for_delete:
            manager.filter(id__in=ids_for_delete).delete()

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновляет профиль артиста и синхронизирует контакты и соцсети."""
        contacts_data = validated_data.pop('contacts', None)
        socials_data = validated_data.pop('socials', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if contacts_data is not None:
            self._sync_nested_items(
                instance,
                contacts_data,
                ArtistContact,
                'contacts',
            )
        if socials_data is not None:
            self._sync_nested_items(
                instance,
                socials_data,
                ArtistSocial,
                'socials',
            )
        return instance

    class Meta:
        model = ArtistProfile
        fields = (
            'name',
            'description',
            'city',
            'url',
            'socials',
            'contacts',
        )


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
        """Создает профиль артиста для текущего пользователя."""
        user = self.context['request'].user
        ensure_listener_profile(user)
        try:
            return ArtistProfile.objects.create(
                user=user,
                **validated_data,
            )
        except IntegrityError:
            if ArtistProfile.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {'detail': 'У пользователя уже есть профиль артиста.'},
                )
            raise
