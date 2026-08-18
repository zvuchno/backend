"""Сериализаторы для работы с альбомами и их коммерческими данными.

Содержит классы для чтения и записи данных модели Album, включая
автоматическое создание связанных объектов Product и ProductVariant.
Используются в API для создания и обновления альбомов и их товарных данных.
"""

from django.utils import timezone
from rest_framework import serializers

from .mixins import ImmutableFieldsSerializerMixin
from store.constants import (
    CHAR_PRESET_DIGITAL,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Album


class AlbumReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Album."""

    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    sku = serializers.SerializerMethodField()
    artist_name = serializers.CharField(
        source='artist.name',
        read_only=True,
    )

    class Meta:
        model = Album
        fields = (
            'id',
            'sku',
            'name',
            'artist_name',
            'is_single',
            'price',
            'cover_image',
            'is_published',
        )

    def get_sku(self, obj) -> str | None:
        product = getattr(obj, 'product', None)
        if not product:
            return None

        variant = next(
            (
                v
                for v in product.variants.all()
                if v.is_active and v.property_value == CHAR_PRESET_DIGITAL
            ),
            None,
        )
        return variant.sku if variant else None


class AlbumReadDetailSerializer(AlbumReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Album."""

    allow_overpay = serializers.SerializerMethodField()
    genre_id = serializers.ReadOnlyField()
    genre = serializers.StringRelatedField()
    artist_id = serializers.ReadOnlyField()

    class Meta(AlbumReadSerializer.Meta):
        fields = AlbumReadSerializer.Meta.fields + (
            'artist_id',
            'genre_id',
            'genre',
            'description',
            'release_date',
            'allow_overpay',
            'visibility',
        )

    def get_allow_overpay(self, obj) -> bool:
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False


class AlbumWriteSerializer(
    ImmutableFieldsSerializerMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для создания и обновления Album."""

    immutable_fields = ('artist',)

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=True,
    )
    allow_overpay = serializers.BooleanField(required=False)

    class Meta:
        model = Album
        fields = (
            'name',
            'artist',
            'is_single',
            'release_date',
            'genre',
            'price',
            'description',
            'cover_image',
            'allow_overpay',
            'visibility',
            'is_published',
        )
        extra_kwargs = {
            'artist': {
                'required': False,
            },
        }

    def validate_release_date(self, value):
        if value is None:
            return value

        if value > timezone.now().date():
            raise serializers.ValidationError(
                'Дата релиза не может быть в будущем.',
            )

        return value

    def create(self, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        return super().update(instance, validated_data)
