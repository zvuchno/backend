from rest_framework import serializers

from users.models import ArtistStoreSettings


class ArtistStoreSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор настроек магазина артиста или лейбла."""

    class Meta:
        model = ArtistStoreSettings
        fields = (
            'support_email',
            'returns_email',
        )
