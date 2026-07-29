from django.db.models import Sum
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.constants import (
    CHAR_PRESET_DIGITAL,
    CHAR_PRESET_SIMPLE,
    DEFAULT_QUANTITY,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Merch, ProductVariant
from store.serializers import ImageSerializer
from store.serializers.mixins import ImmutableFieldsSerializerMixin


def validate_not_reserved(value):
    """Проверяет, что значение не совпадает с зарезервированными пресетами."""
    if value in (CHAR_PRESET_SIMPLE, CHAR_PRESET_DIGITAL):
        raise serializers.ValidationError(
            f'Значение "{value}" зарезервировано '
            'системой и недоступно для использования.',
        )
    return value


class MerchReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Merch."""

    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    sku = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Merch
        fields = (
            'id',
            'sku',
            'name',
            'description',
            'price',
            'stock',
            'main_image',
            'is_published',
        )

    def get_sku(self, obj) -> str | None:
        product = getattr(obj, 'product', None)
        if not product or product.property_name:
            return None

        simple = next(
            (
                v
                for v in product.variants.all()
                if v.is_active and v.property_value == CHAR_PRESET_SIMPLE
            ),
            None,
        )
        return simple.sku if simple else None

    def get_stock(self, obj) -> int:
        product = getattr(obj, 'product', None)
        if not product:
            return 0

        active_variants = product.variants.filter(is_active=True)

        if not product.property_name:
            simple = active_variants.filter(
                property_value=CHAR_PRESET_SIMPLE,
            ).first()
            return (simple.stock or 0) if simple else 0
        total_stock = active_variants.exclude(
            property_value=CHAR_PRESET_SIMPLE,
        ).aggregate(total=Sum('stock'))['total']

        return total_stock or 0

    def get_main_image(self, obj) -> str | None:
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
    kind = serializers.StringRelatedField()
    album = serializers.StringRelatedField()
    variants = serializers.SerializerMethodField()
    property_name = serializers.CharField(
        source='product.property_name',
        read_only=True,
    )

    class Meta(MerchReadSerializer.Meta):
        fields = MerchReadSerializer.Meta.fields + (
            'allow_overpay',
            'images_merch',
            'kind',
            'album',
            'property_name',
            'variants',
            'visibility',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop('main_image', None)
        return data

    def get_allow_overpay(self, obj) -> bool:
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

        return VariantReadSerializer(qs, many=True).data


class VariantWriteSerializer(serializers.Serializer):
    """Сериализатор для записи варианта мерча."""

    id = serializers.IntegerField(required=False)
    value = serializers.CharField(
        source='property_value',
        validators=[validate_not_reserved],
    )
    stock = serializers.IntegerField(min_value=DEFAULT_QUANTITY, required=True)


class MerchWriteSerializer(
    ImmutableFieldsSerializerMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для создания и обновления Merch."""

    immutable_fields = ('artist',)

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
            'artist',
            'description',
            'allow_overpay',
            'visibility',
            'is_published',
            'property_name',
            'stock',
            'variants',
        )
        extra_kwargs = {
            'artist': {
                'required': False,
            },
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('variants') and attrs.get('stock') is not None:
            raise serializers.ValidationError({
                'stock': 'Нельзя указывать stock вместе с variants. '
                'Укажите stock внутри каждого варианта.',
            })
        variants = attrs.get('variants')
        if variants is not None and not variants:
            attrs['property_name'] = ''
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
