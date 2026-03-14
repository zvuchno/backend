from django.utils import timezone
from rest_framework import serializers

from store.models import Album


class AlbumReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Album."""

    owner = serializers.ReadOnlyField(source='user.username')
    genre = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Album
        fields = (
            'id',
            'name',
            'is_single',
            'release_date',
            'genre',
            'price',
            'description',
            'cover_image',
            'allow_fans_overpay',
            'visibility',
            'is_published',
            'is_active',
            'owner',
        )

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        owner = self.context['request'].user

        # Если юзер не владелец, удаляем поле из ответа
        if owner != instance.owner:
            ret.pop('visibility', None)
        return ret


class AlbumWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Album."""

    class Meta:
        model = Album
        fields = (
            'name',
            'is_single',
            'release_date',
            'genre',
            'price',
            'description',
            'cover_image',
            'allow_fans_overpay',
            'visibility',
            'is_published',
            'is_active',
        )

    def validate_release_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                'Дата релиза не может быть в будущем.',
            )
        return value
