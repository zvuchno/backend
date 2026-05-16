"""Сериализатор для получения вариантов доставки."""

from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Delivery


class DeliverySerializer(serializers.ModelSerializer):
    """Сериализатор для Delivery."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )

    class Meta:
        model = Delivery
        fields = ('id', 'name', 'delivery_type', 'price', 'description')
