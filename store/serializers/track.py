"""
Сериализаторы для работы с треками.

Содержит сериализаторы для чтения и записи данных модели Track,
используемые в API музыкального каталога.
"""

from rest_framework import serializers

from store.models import Track


class TrackSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Track."""

    class Meta:
        model = Track
        fields = (
            'name',
            'album',
            'audio_file',
            'individual_price',
            'allow_fans_overpay',
            'lyrics',
        )
