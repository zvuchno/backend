"""Сериализаторы витринных detail-ручек каталога."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.constants import (
    CHAR_PRESET_SIMPLE,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import ProductVariant
from store.serializers import (
    ImageSerializer,
    VariantKeySerializer,
)


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


class CatalogReleaseVariantSerializer(serializers.ModelSerializer):
    """Вариант покупки релиза в витринной detail карточке."""

    variant_key = serializers.SerializerMethodField(
        help_text='Ключ для сопоставления с selected_variant_key каталога.',
    )
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
            'variant_key',
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

    @extend_schema_field(VariantKeySerializer)
    def get_variant_key(self, obj) -> dict:
        """Возвращает ключ варианта покупки."""
        product = obj.product

        if product.album_id:
            return {
                'type': 'album',
                'id': product.album_id,
            }

        return {
            'type': 'merch',
            'id': product.merch_id,
        }

    def get_images(self, obj) -> list[dict]:
        """Возвращает изображения варианта покупки."""
        images = self._get_image_items(obj)

        return ImageSerializer(
            images,
            many=True,
            context=self.context,
        ).data

    def _get_image_items(self, obj) -> list[dict]:
        """Возвращает изображения в едином формате."""
        product = obj.product

        if product.album_id:
            return self._get_album_image_items(product.album)

        return self._get_merch_image_items(product.merch)

    @staticmethod
    def _get_album_image_items(album) -> list[dict]:
        """Возвращает обложку альбома как список изображений."""
        if not album.cover_image:
            return []

        return [
            {
                'image': album.cover_image,
                'is_main': True,
            },
        ]

    def _get_merch_image_items(self, merch) -> list[dict]:
        """Возвращает изображения мерча.

        Если у носителя нет собственных изображений, возвращает
        обложку связанного альбома как fallback.
        """
        images = list(getattr(merch, 'prefetched_images', []))

        if not images:
            album = getattr(merch, 'album', None)
            if album:
                return self._get_album_image_items(album)
            return []

        has_main = any(image.is_main for image in images)

        return [
            {
                'image': image.image,
                'is_main': image.is_main or (index == 0 and not has_main),
            }
            for index, image in enumerate(images)
        ]

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


class CatalogReleaseDetailSerializer(CatalogDetailBaseSerializer):
    """Витринная detail-карточка релиза."""

    is_single = serializers.BooleanField()
    genre = serializers.CharField()
    release_date = serializers.DateField()
    property_name = serializers.CharField(default='Формат')
    variants = serializers.SerializerMethodField()

    def get_images(self, obj) -> list[dict]:
        """Возвращает изображения альбома в формате галереи."""
        if not obj.cover_image:
            return []

        return ImageSerializer(
            [{'image': obj.cover_image, 'is_main': True}],
            many=True,
            context=self.context,
        ).data

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


class CatalogMerchDetailSerializer(CatalogDetailBaseSerializer):
    """Витринная detail-карточка обычного мерча."""

    kind = serializers.SerializerMethodField()
    property_name = serializers.CharField(
        source='product.property_name',
    )
    stock = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    def get_images(self, obj) -> list[dict]:
        """Возвращает изображения мерча."""
        images = list(getattr(obj, 'prefetched_images', []))

        if not images:
            return []

        has_main = any(image.is_main for image in images)

        return ImageSerializer(
            [
                {
                    'image': image.image,
                    'is_main': image.is_main or (index == 0 and not has_main),
                }
                for index, image in enumerate(images)
            ],
            many=True,
            context=self.context,
        ).data

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
