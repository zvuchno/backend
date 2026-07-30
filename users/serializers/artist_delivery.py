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
