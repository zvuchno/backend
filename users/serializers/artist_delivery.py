from rest_framework import serializers

from users.models import ArtistPickupPoint, ArtistShippingPoint


class ArtistPickupPointManageSerializer(serializers.ModelSerializer):
    """Сериализатор управления точкой самовывоза артиста."""

    class Meta:
        model = ArtistPickupPoint
        fields = (
            'id',
            'address',
            'pickup_date',
            'is_active',
        )
        read_only_fields = ('id',)

    def validate(self, attrs):
        """Запрещает дублирование активной точки артиста."""
        artist = self.context['view'].get_artist_profile()

        address = attrs.get(
            'address',
            getattr(self.instance, 'address', None),
        )
        pickup_date = attrs.get(
            'pickup_date',
            getattr(self.instance, 'pickup_date', None),
        )
        is_active = attrs.get(
            'is_active',
            getattr(self.instance, 'is_active', True),
        )

        if not is_active:
            return attrs

        duplicates = ArtistPickupPoint.objects.filter(
            artist=artist,
            address=address,
            pickup_date=pickup_date,
            is_active=True,
        )

        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise serializers.ValidationError({
                'non_field_errors': (
                    'Активная точка самовывоза с таким адресом '
                    'и датой уже существует.'
                ),
            })

        return attrs


class ArtistShippingPointSerializer(serializers.ModelSerializer):
    """Сериализатор ПВЗ СДЭК для отправки заказов артиста."""

    class Meta:
        model = ArtistShippingPoint
        fields = (
            'pvz_code',
            'city_code',
            'city',
            'address',
        )
