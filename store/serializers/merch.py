"""Сериализаторы для обработки данных мерча."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .mixins import BaseCatalogItemSerializerMixin
from store.constants import (
    CHAR_PRESET_DIGITAL,
    CHAR_PRESET_SIMPLE,
    DEFAULT_QUANTITY,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Merch, ProductVariant
from store.serializers import ImageSerializer


def validate_not_reserved(value):
    """Проверяет, что значение не совпадает с зарезервированными пресетами."""
    if value in (CHAR_PRESET_SIMPLE, CHAR_PRESET_DIGITAL):
        raise serializers.ValidationError(
            f'Значение "{value}" зарезервировано '
            'системой и недоступно для использования.',
        )
    return value


class MerchReadSerializer(
    BaseCatalogItemSerializerMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для чтения Merch."""

    artist_name = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    product_type = serializers.CharField(
        source='product.product_type',
        read_only=True,
    )

    class Meta(BaseCatalogItemSerializerMixin.Meta):
        model = Merch

    def get_image(self, obj):
        request = self.context.get('request')
        images = list(obj.images_merch.all())

        for image in images:
            if image.is_main:
                url = image.image.url
                return request.build_absolute_uri(url) if request else url

        first = images[0] if images else None
        if first:
            url = first.image.url
            return request.build_absolute_uri(url) if request else url

        return None

    def get_kind(self, obj):
        return obj.kind.name

    def get_year(self, obj):
        if obj.is_carrier and obj.album_id:
            if obj.album.release_date:
                return obj.album.release_date.year
        return None


class VariantReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения варианта мерча."""

    value = serializers.CharField(source='property_value')

    class Meta:
        model = ProductVariant
        fields = ('id', 'sku', 'stock', 'value')


class MerchDetailSerializer(MerchReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Merch."""

    allow_overpay = serializers.SerializerMethodField()
    images_merch = ImageSerializer(many=True, read_only=True)
    album = serializers.StringRelatedField()
    variants = serializers.SerializerMethodField()
    property_name = serializers.CharField(
        source='product.property_name',
        read_only=True,
    )
    stock = serializers.SerializerMethodField()

    class Meta(MerchReadSerializer.Meta):
        fields = MerchReadSerializer.Meta.fields + (
            'allow_overpay',
            'images_merch',
            'album',
            'description',
            'property_name',
            'stock',
            'variants',
            'visibility',
            'is_published',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop('image', None)

        request = self.context.get('request')
        user = request.user if request else None

        if not user or not (
            user.is_authenticated and (user == instance.owner or user.is_staff)
        ):
            data.pop('visibility', None)
            data.pop('is_published', None)

        return data

    def get_stock(self, obj):
        product = getattr(obj, 'product', None)
        if not product:
            return 0

        variants = list(product.variants.all())

        if not product.property_name:
            simple = next(
                (
                    v
                    for v in variants
                    if v.property_value == CHAR_PRESET_SIMPLE and v.is_active
                ),
                None,
            )
            return simple.stock if simple else 0

        return sum(
            v.stock
            for v in variants
            if v.is_active and v.property_value != CHAR_PRESET_SIMPLE
        )

    def get_allow_overpay(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False

    @extend_schema_field(VariantReadSerializer(many=True))
    def get_variants(self, obj):
        product = getattr(obj, 'product', None)
        if not product:
            return []

        if not product.property_name:
            simple = product.variants.filter(
                property_value=CHAR_PRESET_SIMPLE,
                is_active=True,
            ).first()
            if simple:
                data = VariantReadSerializer(simple).data
                data['value'] = ''
                return [data]

            return []

        request = self.context.get('request')
        is_owner = request and request.user == obj.owner

        qs = (
            product.variants
            .filter(
                is_active=True,
            )
            .exclude(
                property_value=CHAR_PRESET_SIMPLE,
            )
            .order_by('id')
        )

        if not is_owner:
            qs = qs.exclude(stock=0)

        return VariantReadSerializer(qs, many=True).data


class VariantWriteSerializer(serializers.Serializer):
    """Сериализатор для записи варианта мерча."""

    id = serializers.IntegerField(required=False)
    value = serializers.CharField(
        source='property_value',
        validators=[validate_not_reserved],
    )
    stock = serializers.IntegerField(min_value=DEFAULT_QUANTITY, required=True)


class MerchWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Merch."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=True,
        write_only=True,
    )
    allow_overpay = serializers.BooleanField(required=False)
    property_name = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[validate_not_reserved],
    )
    variants = VariantWriteSerializer(many=True, required=False)
    stock = serializers.IntegerField(min_value=0, required=False)

    class Meta:
        model = Merch
        fields = (
            'name',
            'kind',
            'price',
            'album',
            'description',
            'allow_overpay',
            'visibility',
            'is_published',
            'property_name',
            'stock',
            'variants',
        )

    def validate(self, attrs):
        if attrs.get('variants') and attrs.get('stock') is not None:
            raise serializers.ValidationError({
                'stock': 'Нельзя указывать stock вместе с variants. '
                'Укажите stock внутри каждого варианта.',
            })
        return attrs

    def to_representation(self, instance):
        return MerchDetailSerializer(instance, context=self.context).data

    def create(self, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        validated_data.pop('variants', None)
        validated_data.pop('property_name', None)
        validated_data.pop('stock', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        validated_data.pop('variants', None)
        validated_data.pop('property_name', None)
        validated_data.pop('stock', None)
        return super().update(instance, validated_data)
