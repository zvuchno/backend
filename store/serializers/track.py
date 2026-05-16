"""Сериализаторы для работы с треками.

Содержит сериализаторы для чтения и записи данных модели Track,
используемые в API.
TODO: Реализовать логику покупки аудиофайла:
- ссылка на загрузку только купившему?
- в списке треков отдавать демку?
"""

from decimal import Decimal

from rest_framework import serializers

from .mixins import ProductVariantsMixin
from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Track


class TrackReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Track."""

    price = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = (
            'id',
            'name',
            'album',
            'duration',
            'position',
            'price',
        )

    def get_price(self, obj) -> Decimal | None:
        product = getattr(obj, 'product', None)
        if product:
            return product.price
        return None


class TrackReadDetailSerializer(ProductVariantsMixin, TrackReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Track."""

    allow_overpay = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    class Meta(TrackReadSerializer.Meta):
        fields = TrackReadSerializer.Meta.fields + (
            'audio_file',
            'allow_overpay',
            'description',
            'variants',
        )

    def get_allow_overpay(self, obj) -> bool:
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False


class TrackWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=True,
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
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        return super().update(instance, validated_data)
