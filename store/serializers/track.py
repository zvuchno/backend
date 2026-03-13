"""
Сериализаторы для работы с треками.

Содержит сериализаторы для чтения и записи данных модели Track,
используемые в API.
"""

from rest_framework import serializers

from store.models import Track


class TrackReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Track."""

    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Track
        fields = (
            'id',
            'name',
            'album',
            'audio_file',
            'track_number',
            'duration',
            'individual_price',
            'allow_fans_overpay',
            'lyrics',
            'owner'
        )
        read_only_fields = ('duration', 'owner')


class TrackWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления."""

    class Meta:
        model = Track
        fields = (
            'name',
            'album',
            'audio_file',
            'track_number',
            'individual_price',
            'allow_fans_overpay',
            'lyrics',
        )
