"""Сериализатор для работы со справосником носителей."""

from rest_framework import serializers

from store.models import Carrier


class CarrierSerializer(serializers.ModelSerializer):
    """Сериализатор модели Carrier."""

    class Meta:
        model = Carrier
        fields = ('id', 'name', 'slug')
