import logging

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


logger = logging.getLogger(__name__)


def get_active_variants(product) -> list[ProductVariant]:
    """Возвращает активные варианты продукта.

    Ожидает, что `active_variants` был заранее подготовлен через
    `Prefetch` во view.
    Если prefetch отсутствует — делает fallback-запрос и логирует
    предупреждение, чтобы деградация производительности не осталась
    незамеченной.
    """
    variants = getattr(product, 'active_variants', None)
    if variants is None:
        logger.debug(
            'active_variants не был prefetch-нут для Product id=%s. '
            'Используется fallback-запрос — проверь get_queryset() '
            'вьюсета/сериализатора на предмет отсутствующего Prefetch.',
            product.id,
        )
        variants = list(
            product.variants.filter(is_active=True),
        )
        product.active_variants = variants
    return variants


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
    artist_name = serializers.CharField(
        source='artist.name',
        read_only=True,
    )

    class Meta:
        model = Merch
        fields = (
            'id',
            'sku',
            'name',
            'artist_name',
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
                variant
                for variant in get_active_variants(product)
                if variant.property_value == CHAR_PRESET_SIMPLE
            ),
            None,
        )
        return simple.sku if simple else None

    def get_stock(self, obj) -> int:
        product = getattr(obj, 'product', None)
        if not product:
            return 0

        variants = get_active_variants(product)

        if not product.property_name:
            simple = next(
                (
                    variant
                    for variant in variants
                    if variant.property_value == CHAR_PRESET_SIMPLE
                ),
                None,
            )
            return simple.stock or 0 if simple else 0

        return sum(
            variant.stock or 0
            for variant in variants
            if variant.property_value != CHAR_PRESET_SIMPLE
        )

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
    kind_id = serializers.ReadOnlyField()
    kind = serializers.StringRelatedField()
    album_id = serializers.ReadOnlyField()
    album = serializers.StringRelatedField()
    variants = serializers.SerializerMethodField()
    property_name = serializers.CharField(
        source='product.property_name',
        read_only=True,
    )
    artist_id = serializers.ReadOnlyField()

    class Meta(MerchReadSerializer.Meta):
        fields = MerchReadSerializer.Meta.fields + (
            'artist_id',
            'allow_overpay',
            'images_merch',
            'kind_id',
            'kind',
            'album_id',
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
        if not product or not product.property_name:
            return []

        variants = [
            variant
            for variant in get_active_variants(product)
            if variant.property_value != CHAR_PRESET_SIMPLE
        ]

        return VariantReadSerializer(variants, many=True).data


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
