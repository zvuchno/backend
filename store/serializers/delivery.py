"""Сериализатор для получения вариантов доставки."""

from rest_framework import serializers

from store.models import Delivery


class DeliverySerializer(serializers.ModelSerializer):
    """Сериализатор для Delivery."""

    class Meta:
        model = Delivery
        fields = ('id', 'name', 'price', 'description')
