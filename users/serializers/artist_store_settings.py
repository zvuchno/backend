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
        """Проверяет возможность включения способов доставки."""
        attrs = super().validate(attrs)

        artist = self.context['artist']

        shipping_enabled = attrs.get(
            'shipping_enabled',
            getattr(self.instance, 'shipping_enabled', False),
        )
        pickup_enabled = attrs.get(
            'pickup_enabled',
            getattr(self.instance, 'pickup_enabled', False),
        )

        if shipping_enabled:
            shipping_point = getattr(artist, 'shipping_point', None)

            if shipping_point is None or not shipping_point.is_configured:
                raise serializers.ValidationError({
                    'shipping_enabled': (
                        'Сначала укажите ПВЗ СДЭК для отправки заказов.'
                    ),
                })

        if (
            pickup_enabled
            and not artist.pickup_points.filter(is_active=True).exists()
        ):
            raise serializers.ValidationError({
                'pickup_enabled': (
                    'Сначала добавьте активную точку самовывоза.'
                ),
            })

        return attrs
