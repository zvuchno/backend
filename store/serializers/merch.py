from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, PRICE_DECIMAL_PLACES
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
        for image in obj.images_merch.all():
            if image.is_main:
                return image.image.url
        return None


class VariantReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения варианта мерча."""

    characteristics = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ('id', 'sku', 'stock', 'characteristics')

    def get_characteristics(self, obj):
        return obj.characteristic or {}


class MerchDetailSerializer(MerchReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Merch."""

    allow_overpay = serializers.SerializerMethodField()
    images_merch = ImageSerializer(many=True, read_only=True)
    kind = serializers.StringRelatedField()
    album = serializers.StringRelatedField()
    variants = serializers.SerializerMethodField()

    class Meta(MerchReadSerializer.Meta):
        fields = MerchReadSerializer.Meta.fields + (
            'allow_overpay',
            'images_merch',
            'kind',
            'album',
            'visibility',
            'is_published',
            'is_active',
            'variants',
        )

    def get_allow_overpay(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False

    def get_variants(self, obj):
        product = getattr(obj, 'product', None)
        if not product:
            return []
        qs = product.variants.all().order_by('id')
        return VariantReadSerializer(qs, many=True).data


class VariantWriteSerializer(serializers.Serializer):
    """Сериализатор для записи варианта мерча."""

    stock = serializers.IntegerField(min_value=0, required=True)
    characteristics = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=True,
        help_text='JSON',
    )

    def update(self, instance, validated_data):
        instance.stock = validated_data.get('stock', instance.stock)
        instance.characteristic = validated_data.get(
            'characteristics', instance.characteristic
        )
        instance.save(update_fields=['stock', 'characteristic'])
        return instance


class MerchWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Merch."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        required=True,
        write_only=True,
    )
    allow_overpay = serializers.BooleanField(required=False)
    variants = VariantWriteSerializer(many=True, required=False)

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
            'variants',
        )

    def to_representation(self, instance):
        return MerchDetailSerializer(instance).data

    def create(self, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        validated_data.pop('variants', None)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        validated_data.pop('variants', None)

        return super().update(instance, validated_data)
