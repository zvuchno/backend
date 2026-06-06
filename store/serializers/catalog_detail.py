"""Сериализаторы витринных detail-ручек каталога."""

from rest_framework import serializers

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Album, ProductVariant
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
        if product.album_id:
            return ''
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
        if product.album_id:
            return ''

        return product.content.description

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
    serializers.ModelSerializer,
):
    """Витринная detail-карточка релиза."""

    album_name = serializers.CharField(
        source='name',
        help_text='Название альбома.',
    )
    artist_name = serializers.SerializerMethodField(
        help_text='Имя артиста или коллектива.',
    )
    variants = serializers.SerializerMethodField(
        help_text='Варианты покупки альбома.',
    )

    class Meta:
        model = Album
        fields = (
            'id',
            'artist_name',
            'album_name',
            'is_single',
            'description',
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
    MerchDetailSerializer,
    CatalogDetailBaseSerializer,
):
    """Вариант обычного мерча в витринной detail странице."""

    class Meta(MerchDetailSerializer.Meta):
        fields = MerchDetailSerializer.Meta.fields + ('artist_name',)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        data['images'] = data.pop('images_merch', [])
        data.pop('album', None)
        data.pop('visibility', None)
        data.pop('is_published', None)

        for variant in data.get('variants', []):
            variant['variant_id'] = variant.pop('id', None)
            variant['property_value'] = variant.pop('value', '')

        return data
