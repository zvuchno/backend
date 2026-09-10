from rest_framework import serializers

from users.models import ArtistStoreSettings


class ArtistStoreSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор настроек магазина артиста или лейбла."""

    class Meta:
        model = ArtistStoreSettings
        fields = (
            'support_email',
            'returns_email',
            'shipping_enabled',
            'pickup_enabled',
        )

    def validate(self, attrs):
        """Проверяет возможность включения доставки СДЭК."""
        attrs = super().validate(attrs)

        shipping_enabled = attrs.get(
            'shipping_enabled',
            getattr(self.instance, 'shipping_enabled', False),
        )

        if not shipping_enabled:
            return attrs

        artist = self.context['artist']
        shipping_point = getattr(artist, 'shipping_point', None)

        if shipping_point is None or not shipping_point.is_configured:
            raise serializers.ValidationError({
                'shipping_enabled': (
                    'Сначала укажите ПВЗ СДЭК для отправки заказов.'
                ),
            })

        return attrs
