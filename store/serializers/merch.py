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


class MerchReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Merch."""

    price = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Merch
        fields = (
            'id',
            'name',
            'description',
            'price',
            'main_image',
        )

    def get_price(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.price
        return None

    def get_main_image(self, obj):
        request = self.context.get('request')

        for image in obj.images_merch.all():
            if image.is_main:
                url = image.image.url
                return request.build_absolute_uri(url) if request else url

        first = obj.images_merch.first()
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
    property_name = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()

    class Meta(MerchReadSerializer.Meta):
        fields = MerchReadSerializer.Meta.fields + (
            'allow_overpay',
            'images_merch',
            'kind',
            'album',
            'property_name',
            'stock',
            'variants',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop('main_image', None)
        request = self.context.get('request')
        if request and request.user == instance.owner:
            for field in ('visibility', 'is_published', 'is_active'):
                data[field] = getattr(instance, field)
        return data

    def get_stock(self, obj):
        product = getattr(obj, 'product', None)
        if not product:
            return 0

        # если нет свойств - берём stock простого варианта
        if not product.property_name:
            simple = product.variants.filter(
                property_value=CHAR_PRESET_SIMPLE,
                is_active=True
            ).first()
            return simple.stock if simple else 0

        # если есть свойства - сумма стоков всех вариантов
        return product.variants.filter(is_active=True).exclude(
            property_value=CHAR_PRESET_SIMPLE
        ).aggregate(total=Sum('stock'))['total'] or 0

    def get_allow_overpay(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False

    def get_property_name(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.property_name
        return None

    @extend_schema_field(VariantReadSerializer(many=True))
    def get_variants(self, obj):
        product = getattr(obj, 'product', None)
        if not product or not product.property_name:
            return []

        request = self.context.get('request')
        is_owner = request and request.user == obj.owner

        qs = product.variants.filter(
            is_active=True,
        ).exclude(
            property_value=CHAR_PRESET_SIMPLE,
        ).order_by('id')

        if not is_owner:
            qs = qs.exclude(stock=0)

        return VariantReadSerializer(qs, many=True).data


class VariantWriteSerializer(serializers.Serializer):
    """Сериализатор для записи варианта мерча."""

    id = serializers.IntegerField(required=False)
    value = serializers.CharField(source='property_value')
    stock = serializers.IntegerField(min_value=DEFAULT_QUANTITY, required=True)

    def validate_value(self, value):
        if value in (CHAR_PRESET_SIMPLE, CHAR_PRESET_DIGITAL):
            raise serializers.ValidationError(
                f'Значение "{value}" зарезервировано '
                'системой и недоступно для использования.'
            )
        return value


class MerchWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Merch."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=True,
        write_only=True,
    )
    allow_overpay = serializers.BooleanField(required=False)
    property_name = serializers.CharField(required=False, allow_blank=True)
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
            'is_active',
            'property_name',
            'stock',
            'variants',
        )

    def validate_property_name(self, value):
        if value in (CHAR_PRESET_SIMPLE, CHAR_PRESET_DIGITAL):
            raise serializers.ValidationError(
                f'Значение "{value}" зарезервировано системой '
                'и недоступно для использования.'
            )
        return value

    def validate(self, attrs):
        if attrs.get('variants') and attrs.get('stock') is not None:
            raise serializers.ValidationError({
                'stock': 'Нельзя указывать stock вместе с variants. '
                        'Укажите stock внутри каждого варианта.'
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
