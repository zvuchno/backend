"""Сериализаторы витринных detail-ручек каталога."""

from rest_framework import serializers

from store.constants import (
    CHAR_PRESET_SIMPLE,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Album, Merch, ProductVariant
from store.serializers.mixins import (
    ProductImagesMixin,
    ProductVariantsMixin,
)


class CatalogDetailBaseSerializer(ProductImagesMixin, serializers.Serializer):
    """Базовый сериализатор витринной detail-карточки."""

    artist_name = serializers.SerializerMethodField()
    artist_image = serializers.SerializerMethodField()

    def get_artist_name(self, obj) -> str | None:
        """Возвращает имя артиста-владельца."""
        artist = getattr(obj, 'artist', None)
        if artist is None:
            return None
        return artist.name

    def get_artist_image(self, obj) -> str | None:
        """Возвращает изображение артиста."""
        artist = getattr(obj, 'artist', None)
        if artist is None:
            return None
        return self.get_image_url(artist.cover)


class CatalogReleaseVariantSerializer(
    ProductImagesMixin,
    serializers.ModelSerializer,
):
    """Вариант покупки релиза в витринной detail карточке."""

    property_value = serializers.SerializerMethodField(
        help_text='Формат носителя: диджитал, винил, кассета и т.п.',
    )
    name = serializers.SerializerMethodField(
        help_text='Название варианта покупки.',
    )
    variant_id = serializers.IntegerField(
        source='id',
        help_text='ID Variant для добавления в корзину.',
    )
    is_available_for_purchase = serializers.BooleanField(
        read_only=True,
    )
    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        help_text='Цена варианта покупки.',
    )
    allow_overpay = serializers.SerializerMethodField(
        help_text='Возможность переплаты.',
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
            'variant_id',
            'is_available_for_purchase',
            'sku',
            'stock',
            'property_value',
            'name',
            'price',
            'allow_overpay',
            'description',
            'images',
        )
        read_only_fields = fields

    def get_allow_overpay(self, obj) -> bool:
        """Возвращает доступность переплаты."""
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False

    def get_name(self, obj) -> str:
        """Возвращает название варианта покупки."""
        product = getattr(obj, 'product', None)
        return product.name

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
        return product.content.description

    def get_property_value(self, obj) -> str:
        """Возвращает формат варианта покупки."""
        product = obj.product

        if product.album_id:
            return 'Диджитал'

        merch = product.merch
        kind = getattr(merch, 'kind', None)
        kind_name = kind.name if kind else 'Физический носитель'

        if (
            not product.property_name
            or obj.property_value == CHAR_PRESET_SIMPLE
        ):
            return kind_name

        return f'{kind_name} — {obj.property_value}'


class CatalogReleaseDetailSerializer(
    ProductVariantsMixin,
    CatalogDetailBaseSerializer,
    serializers.ModelSerializer,
):
    """Витринная detail-карточка релиза."""

    variants = serializers.SerializerMethodField(
        help_text='Варианты покупки альбома.',
    )

    class Meta:
        model = Album
        fields = (
            'id',
            'artist_name',
            'artist_image',
            'is_single',
            'variants',
        )

    def get_variants(self, obj) -> list[dict]:
        """Возвращает варианты покупки релиза."""
        variants = []

        product = getattr(obj, 'product', None)
        if product is not None:
            variants.extend(getattr(product, 'active_digital_variants', []))

        for carrier in getattr(obj, 'active_carriers', []):
            product = getattr(carrier, 'product', None)
            if product is None:
                continue

            carrier_variants = self.select_product_variants(
                product,
                getattr(product, 'active_carriers_variants', []),
            )

            variants.extend(carrier_variants)

        return CatalogReleaseVariantSerializer(
            variants,
            many=True,
            context=self.context,
        ).data


class CatalogMerchVariantSerializer(serializers.ModelSerializer):
    """Вариант обычного мерча в витринной detail-карточке."""

    variant_id = serializers.IntegerField(
        source='id',
        read_only=True,
    )
    is_available_for_purchase = serializers.BooleanField(
        read_only=True,
    )
    property_value = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = (
            'variant_id',
            'is_available_for_purchase',
            'sku',
            'stock',
            'property_value',
        )
        read_only_fields = fields

    def get_property_value(self, obj) -> str:
        """Возвращает значение свойства варианта."""
        if obj.property_value == CHAR_PRESET_SIMPLE:
            return ''

        return obj.property_value


class CatalogMerchDetailSerializer(
    ProductVariantsMixin,
    CatalogDetailBaseSerializer,
    serializers.ModelSerializer,
):
    """Вариант обычного мерча в витринной detail странице."""

    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )

    allow_overpay = serializers.BooleanField(
        source='product.allow_overpay',
        read_only=True,
    )
    images = serializers.SerializerMethodField(
        help_text='Изображения мерча.',
    )
    kind = serializers.StringRelatedField()
    property_name = serializers.CharField(
        source='product.property_name',
        read_only=True,
    )
    stock = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    class Meta:
        model = Merch
        fields = (
            'id',
            'name',
            'description',
            'price',
            'artist_name',
            'artist_image',
            'allow_overpay',
            'images',
            'kind',
            'property_name',
            'stock',
            'variants',
        )

    def get_stock(self, obj) -> int:
        """Возвращает общий остаток учитываемых вариантов."""
        product = getattr(obj, 'product', None)
        if product is None:
            return 0

        return self.calculate_product_stock(
            product,
            getattr(product, 'active_catalog_variants', []),
        )

    def get_variants(self, obj) -> list[dict]:
        """Возвращает активные варианты мерча."""
        product = getattr(obj, 'product', None)
        if product is None:
            return []

        variants = self.select_product_variants(
            product,
            getattr(product, 'active_catalog_variants', []),
        )

        return CatalogMerchVariantSerializer(
            variants,
            many=True,
            context=self.context,
        ).data

    def get_images(self, obj) -> list[dict]:
        """Возвращает изображения мерча."""
        items = self.get_merch_image_items(
            getattr(obj, 'prefetched_images', []),
        )
        return self.serialize_image_items(items)
