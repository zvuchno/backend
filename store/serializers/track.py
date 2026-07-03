"""Сериализаторы для работы с треками.

Содержит сериализаторы для чтения и записи данных модели Track,
используемые в API.
"""

from rest_framework import serializers

from .mixins import ProductVariantsMixin
from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Track
from store.services.audio.schedule import TrackGeneratedAudioScheduler


class TrackReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Track."""

    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    allow_overpay = serializers.BooleanField(
        source='product.allow_overpay',
        default=False,
    )
    artist_name = serializers.CharField(
        source='owner.artist_profile.name',
        read_only=True,
        allow_null=True,
    )
    image = serializers.ImageField(
        source='album.cover_image',
        read_only=True,
        allow_null=True,
    )
    is_favorite = serializers.BooleanField(read_only=True)

    class Meta:
        model = Track
        fields = (
            'id',
            'artist_name',
            'name',
            'album',
            'duration',
            'position',
            'price',
            'allow_overpay',
            'image',
            'is_favorite',
        )


class TrackReadDetailSerializer(ProductVariantsMixin, TrackReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Track."""

    variants = serializers.SerializerMethodField()

    class Meta(TrackReadSerializer.Meta):
        fields = TrackReadSerializer.Meta.fields + (
            'audio_file',
            'description',
            'variants',
        )


class TrackWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=False,
    )
    allow_overpay = serializers.BooleanField(required=False)

    class Meta:
        model = Track
        fields = (
            'name',
            'album',
            'audio_file',
            'position',
            'price',
            'allow_overpay',
            'description',
        )

    def create(self, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        track = super().create(validated_data)
        TrackGeneratedAudioScheduler.schedule(track)
        return track

    def update(self, instance, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        audio_file_changed = 'audio_file' in validated_data
        track = super().update(instance, validated_data)
        if audio_file_changed:
            TrackGeneratedAudioScheduler.schedule(track)
        return track

    def validate_album(self, album):
        """Проверяет, что артист работает только со своим альбомом."""
        request = self.context['request']

        if album.owner_id != request.user.id:
            raise serializers.ValidationError(
                'Нельзя добавить трек в чужой альбом.',
            )

        return album
