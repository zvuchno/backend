"""Сериализаторы витринных detail-ручек каталога."""

from rest_framework import serializers

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import ProductVariant
from store.serializers.album import AlbumReadDetailSerializer
from store.serializers.merch import MerchDetailSerializer
from store.serializers.mixins import ProductImagesMixin


class CatalogDetailBaseSerializer(serializers.Serializer):
    """Базовый сериализатор витринной detail-карточки."""

    artist_name = serializers.SerializerMethodField()

    def get_artist_name(self, obj) -> str | None:
        """Возвращает имя артиста-владельца."""
        artist = getattr(obj.owner, 'artist_profile', None)
        if artist is None:
            return None
        return artist.name


class CatalogReleaseVariantSerializer(
    ProductImagesMixin,
    serializers.ModelSerializer,
):
    """Вариант покупки релиза в витринной detail карточке."""

    value = serializers.SerializerMethodField(
        help_text='Формат покупки: диджитал, винил, кассета и т.п.',
    )
    name = serializers.CharField(
        source='product.name',
        help_text='Название варианта покупки.',
    )
    id = serializers.IntegerField(
        help_text='ID Variant для добавления в корзину.',
    )
    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
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
            'id',
            'sku',
            'stock',
            'value',
            'name',
            'price',
            'description',
            'images',
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

        return product.merch.description

    def get_value(self, obj) -> str:
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
    AlbumReadDetailSerializer,
):
    """Витринная detail-карточка релиза."""

    images = serializers.SerializerMethodField()
    property_name = serializers.CharField(default='Формат')
    default_variant_id = serializers.SerializerMethodField(
        help_text='ID цифрового варианта, выбранного по умолчанию.',
    )
    variants = serializers.SerializerMethodField()

    class Meta(AlbumReadDetailSerializer.Meta):
        old_fields = tuple(
            field
            for field in AlbumReadDetailSerializer.Meta.fields
            if field != 'cover_image'
        )
        fields = old_fields + (
            'default_variant_id',
            'images',
            'property_name',
            'variants',
        )

    def get_default_variant_id(self, obj) -> int | None:
        """Возвращает ID цифрового варианта релиза по умолчанию."""
        product = getattr(obj, 'product', None)
        if product is None:
            return None

        variants = getattr(product, 'active_digital_variants', None)
        if variants is not None:
            return variants[0].id if variants else None

        variant = (
            product.variants.filter(is_active=True).order_by('id').first()
        )
        return variant.id if variant else None

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


class CatalogMerchDetailSerializer(
    CatalogDetailBaseSerializer,
    MerchDetailSerializer,
):
    """Вариант обычного мерча в витринной detail странице."""
