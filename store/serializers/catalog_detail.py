"""Сериализаторы витринных detail-ручек каталога."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.constants import (
    CHAR_PRESET_SIMPLE,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import ProductVariant
from store.serializers.mixins import ProductImagesMixin


class CatalogDetailBaseSerializer(serializers.Serializer):
    """Базовый сериализатор витринной detail-карточки."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    artist_name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    description = serializers.CharField()
    images = serializers.SerializerMethodField()

    def get_images(self, obj):
        """Возвращает изображения detail-карточки."""
        raise NotImplementedError

    def get_artist_name(self, obj) -> str | None:
        """Возвращает имя артиста-владельца."""
        artist = getattr(obj.owner, 'artist_profile', None)
        if artist is None:
            return None
        return artist.name

    def get_price(self, obj):
        """Возвращает цену связанного продукта."""
        product = getattr(obj, 'product', None)
        if product is None:
            return None
        return product.price


class CatalogReleaseVariantSerializer(
    ProductImagesMixin,
    serializers.ModelSerializer,
):
    """Вариант покупки релиза в витринной detail карточке."""

    property_value = serializers.SerializerMethodField(
        help_text='Формат покупки: диджитал, винил, кассета и т.п.',
    )
    name = serializers.CharField(
        source='product.name',
        read_only=True,
        help_text='Название варианта покупки.',
    )
    variant_id = serializers.IntegerField(
        source='id',
        read_only=True,
        help_text='ID Variant для добавления в корзину.',
    )
    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
        help_text='Цена варианта покупки.',
    )
    stock = serializers.SerializerMethodField(
        help_text='Остаток. Для цифрового варианта возвращается null.',
    )
    description = serializers.SerializerMethodField(
        help_text='Описание варианта покупки.',
    )
    images = serializers.SerializerMethodField(
        help_text='Изображения варианта покупки.',
    )

    class Meta:
        model = ProductVariant
        fields = (
            'property_value',
            'variant_id',
            'name',
            'price',
            'stock',
            'description',
            'images',
            'sku',
        )
        read_only_fields = fields

    def get_images(self, obj) -> list[dict]:
        """Возвращает изображения варианта покупки."""
        product = obj.product

        if product.album_id:
            items = self.get_album_image_items(product.album)
            return self.serialize_image_items(items)

        merch = product.merch
        items = self.get_merch_image_items(
            getattr(merch, 'prefetched_images', []),
        )

        if not items:
            items = self.get_album_image_items(getattr(merch, 'album', None))

        return self.serialize_image_items(items)

    def get_stock(self, obj) -> int | None:
        """Возвращает остаток варианта. Для цифрового варианта — None."""
        if obj.product.album_id:
            return None

        return obj.stock

    def get_description(self, obj) -> str:
        """Возвращает описание варианта покупки."""
        product = obj.product

        if product.album_id:
            return ''

        return product.merch.description

    def get_property_value(self, obj) -> str:
        """Возвращает формат варианта покупки."""
        product = obj.product

        if product.album_id:
            return 'Диджитал'

        merch = product.merch
        kind = getattr(merch, 'kind', None)

        if not kind:
            return 'Физический носитель'

        return kind.name


class CatalogReleaseDetailSerializer(
    ProductImagesMixin,
    CatalogDetailBaseSerializer,
):
    """Витринная detail-карточка релиза."""

    is_single = serializers.BooleanField()
    genre = serializers.CharField()
    release_date = serializers.DateField()
    property_name = serializers.CharField(default='Формат')
    variants = serializers.SerializerMethodField()

    def get_images(self, obj) -> list[dict]:
        """Возвращает изображения альбома в формате галереи."""
        items = self.get_album_image_items(obj)
        return self.serialize_image_items(items)

    def get_variants(self, obj) -> list[dict]:
        """Возвращает варианты покупки релиза."""
        variants = []

        product = getattr(obj, 'product', None)
        if product is not None:
            variants.extend(getattr(product, 'active_digital_variants', []))

        for carrier in getattr(obj, 'active_carriers', []):
            product = getattr(carrier, 'product', None)
            if product is not None:
                variants.extend(
                    getattr(product, 'active_carriers_variants', []),
                )

        return CatalogReleaseVariantSerializer(
            variants,
            many=True,
            context=self.context,
        ).data


class CatalogMerchVariantSerializer(serializers.ModelSerializer):
    """Вариант обычного мерча в витринной detail странице."""

    variant_id = serializers.IntegerField(
        source='id',
        help_text='ID ProductVariant для добавления в корзину.',
    )
    property_value = serializers.CharField(
        help_text='Значение варианта: размер, цвет и т.п.',
    )

    class Meta:
        model = ProductVariant
        fields = (
            'variant_id',
            'sku',
            'stock',
            'property_value',
        )
        read_only_fields = fields


class CatalogMerchDetailSerializer(
    ProductImagesMixin,
    CatalogDetailBaseSerializer,
):
    """Витринная detail-карточка обычного мерча."""

    kind = serializers.SerializerMethodField()
    property_name = serializers.CharField(
        source='product.property_name',
    )
    stock = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    def get_images(self, obj) -> list[dict]:
        """Возвращает изображения мерча."""
        items = self.get_merch_image_items(
            getattr(obj, 'prefetched_images', []),
        )
        return self.serialize_image_items(items)

    def get_kind(self, obj) -> str | None:
        """Возвращает вид мерча."""
        kind = getattr(obj, 'kind', None)

        if not kind:
            return None

        return kind.name

    def get_stock(self, obj) -> int:
        """Возвращает общий доступный остаток мерча."""
        product = getattr(obj, 'product', None)
        if not product:
            return 0

        variants = self._get_active_variants(product)

        return sum(variant.stock for variant in variants)

    @extend_schema_field(CatalogMerchVariantSerializer(many=True))
    def get_variants(self, obj) -> list[dict]:
        """Возвращает варианты обычного мерча."""
        product = getattr(obj, 'product', None)
        if not product:
            return []

        variants = self._get_active_variants(product)

        if not product.property_name:
            simple = next(
                (
                    variant
                    for variant in variants
                    if variant.property_value == CHAR_PRESET_SIMPLE
                ),
                None,
            )

            if not simple:
                return []

            data = CatalogMerchVariantSerializer(
                simple,
                context=self.context,
            ).data
            data['property_value'] = ''
            return [data]

        variants = [
            variant
            for variant in variants
            if variant.property_value != CHAR_PRESET_SIMPLE
        ]

        return CatalogMerchVariantSerializer(
            variants,
            many=True,
            context=self.context,
        ).data

    @staticmethod
    def _get_active_variants(product) -> list[ProductVariant]:
        """Возвращает активные варианты продукта."""
        variants = getattr(product, 'active_variants', None)

        if variants is not None:
            return list(variants)

        return list(
            product.variants.filter(
                is_active=True,
            ).order_by('id'),
        )
