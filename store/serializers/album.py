"""Сериализаторы для работы с альбомами и их коммерческими данными.

Содержит классы для чтения и записи данных модели Album, включая
автоматическое создание связанных объектов Product и ProductVariant.
Используются в API для создания и обновления альбомов и их товарных данных.
"""

from django.utils import timezone
from rest_framework import serializers

from .mixins import BaseCatalogItemSerializerMixin, ProductVariantsMixin
from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Album


class AlbumReadSerializer(
    BaseCatalogItemSerializerMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для чтения Album."""

    artist_name = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    image = serializers.ImageField(source='cover_image', read_only=True)
    product_type = serializers.CharField(
        source='product.product_type',
        read_only=True,
    )

    class Meta(BaseCatalogItemSerializerMixin.Meta):
        model = Album

    def get_kind(self, obj):
        return 'Сингл' if obj.is_single else 'Альбом'

    def get_year(self, obj):
        if obj.release_date:
            return obj.release_date.year
        return None


class AlbumReadDetailSerializer(ProductVariantsMixin, AlbumReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Album."""

    allow_overpay = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()
    genre = serializers.StringRelatedField()

    class Meta(AlbumReadSerializer.Meta):
        fields = AlbumReadSerializer.Meta.fields + (
            'is_single',
            'genre',
            'description',
            'release_date',
            'allow_overpay',
            'variants',
            'visibility',
            'is_published',
        )

    def get_allow_overpay(self, obj) -> bool:
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = (
            self.context.get('request').user
            if self.context.get('request')
            else None
        )

        # Скрываем поля, если юзера нет, если не владелец и не админ
        if not user or not (
            user.is_authenticated and (user == instance.owner or user.is_staff)
        ):
            data.pop('visibility', None)
            data.pop('is_published', None)
        return data


class AlbumWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Album."""

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

    def validate_release_date(self, value):
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
