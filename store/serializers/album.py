from django.utils import timezone
from rest_framework import serializers

from store.models import Album


class AlbumReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Album."""

    user = serializers.ReadOnlyField(source='user.username')
    genre = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Album
        fields = (
            'id',
            'name',
            'release_date',
            'genre',
            'price',
            'description',
            'cover_image',
            'allow_fans_to_pay_more',
            'visibility',
            'user',
        )

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        user = self.context['request'].user

        # Если юзер не автор, удаляем поле из ответа
        if user != instance.user:
            ret.pop('visibility', None)
        return ret


class AlbumWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Album."""

    class Meta:
        model = Album
        fields = (
            'name',
            'release_date',
            'genre',
            'price',
            'description',
            'cover_image',
            'allow_fans_to_pay_more',
            'visibility',
        )

    def validate_release_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                'Дата релиза не может быть в будущем.'
            )
        return value
