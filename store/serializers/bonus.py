"""Сериализатор для работы с бонусами артистов и лейблов."""

from rest_framework import serializers

from common.access import can_manage_artist

from store.models import Bonus


class BonusReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Bonus."""

    class Meta:
        model = Bonus
        fields = ('id', 'name')


class BonusReadDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Bonus."""

    class Meta(BonusReadSerializer.Meta):
        fields = BonusReadSerializer.Meta.fields + (
            'bonus_file',
            'description',
        )


class BonusWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления бонуса."""

    class Meta:
        model = Bonus
        fields = (
            'id',
            'album',
            'name',
            'bonus_file',
            'description',
        )
        read_only_fields = ('id',)

    def __init__(self, *args, **kwargs):
        """Если вызван для обновления существующего объекта."""
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields['album'].read_only = True

    def validate_album(self, album):
        """Проверяет, что артист работает только со своим альбомом."""
        request = self.context.get('request')

        if (
            request
            and request.user
            and not can_manage_artist(
                request.user,
                album.artist,
            )
        ):
            raise serializers.ValidationError(
                'Нельзя добавить бонус в чужой альбом.',
            )

        return album
