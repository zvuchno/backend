"""Сериализаторы для работы с альбомами и их коммерческими данными.

Содержит классы для чтения и записи данных модели Album, включая
автоматическое создание связанных объектов Product и ProductVariant.
Используются в API для создания и обновления альбомов и их товарных данных.
"""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .image import ImageSerializer
from .mixins import ProductVariantsMixin
from store.constants import (
    CHAR_PRESET_DIGITAL,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import (
    Album,
    Merch,
    ProductVariant,
)


class AlbumReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Album."""

    price = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = (
            'id',
            'name',
            'price',
            'description',
            'cover_image',
            'visibility',
            'is_published',
        )

    def get_price(self, obj) -> Decimal | None:
        product = getattr(obj, 'product', None)
        if product:
            return product.price
        return None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        user = (
            self.context.get('request').user
            if self.context.get('request')
            else None
        )

        # Скрываем поля, если юзера нет, если не владелец и не админ
        if not user or not (
            user.is_authenticated and (user == instance.owner or user.is_staff)
        ):
            ret.pop('visibility', None)
            ret.pop('is_published', None)
        return ret


class AlbumVariantSerializer(serializers.ModelSerializer):
    """Сериализатор варианта покупки альбома."""

    format = serializers.SerializerMethodField()
    name = serializers.CharField(source='product.name')
    product_variant = serializers.IntegerField(source='id')
    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
    )
    allow_overpay = serializers.BooleanField(source='product.allow_overpay')
    stock = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = (
            'format',
            'name',
            'product_variant',
            'price',
            'allow_overpay',
            'stock',
            'description',
            'images',
            'sku',
        )

    def get_images(self, obj):
        """Возвращает изображения варианта покупки."""
        images = self._get_image_items(obj)

        return ImageSerializer(
            images,
            many=True,
            context=self.context,
        ).data

    def _get_image_items(self, obj) -> list[dict] | None:
        """Возвращает изображения в едином формате."""
        product = obj.product

        if product.album_id:
            return self._get_album_image_items(product.album)

        return self._get_merch_image_items(product.merch)

    @staticmethod
    def _get_album_image_items(album) -> list[dict] | None:
        """Возвращает обложку альбома как список изображений."""
        if not album.cover_image:
            return []

        return [
            {
                'image': album.cover_image,
                'is_main': True,
            },
        ]

    def _get_merch_image_items(self, merch) -> list[dict] | None:
        """Возвращает изображения мерча."""
        images = list(merch.images_merch.all())

        if not images:
            # Fallback на обложку альбома, если нет фото носителя.
            album = getattr(merch, 'album', None)
            if album:
                return self._get_album_image_items(album)
            return []

        has_main = any(image.is_main for image in images)
        # если нет главной, выберем главной первую.
        return [
            {
                'image': image.image,
                'is_main': image.is_main or (index == 0 and not has_main),
            }
            for index, image in enumerate(images)
        ]

    def get_stock(self, obj):
        """Возвращает остаток варианта. Для цифрового - None."""
        if obj.product.album_id:
            return None
        return obj.stock

    def get_description(self, obj):
        """Описание варианта. Для цифры - пустое."""
        if obj.product.album_id:
            return ''
        return obj.product.merch.description

    def get_format(self, obj):
        """Возвращает формат варианта покупки."""
        product = obj.product

        if product.album_id:
            return {
                'name': 'Диджитал',
                'slug': CHAR_PRESET_DIGITAL,
            }

        merch = product.merch
        kind = getattr(merch, 'kind', None)

        if not kind:
            return {
                'name': 'Физический носитель',
                'slug': 'carrier',
            }

        return {
            'name': kind.name,
            'slug': kind.slug,
        }


class AlbumReadDetailSerializer(ProductVariantsMixin, AlbumReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Album."""

    variants = serializers.SerializerMethodField()

    class Meta(AlbumReadSerializer.Meta):
        fields = AlbumReadSerializer.Meta.fields + (
            'is_single',
            'genre',
            'release_date',
            'variants',
        )

    def get_variants(self, obj):
        """Возвращает варианты покупки альбома."""
        variants = []

        digital_variant = self._get_digital_variant(obj)
        if digital_variant:
            variants.append(digital_variant)

        variants.extend(self._get_carrier_variants(obj))

        return AlbumVariantSerializer(
            variants,
            many=True,
            context={
                **self.context,
                'album': obj,
            },
        ).data

    def _get_digital_variant(self, album) -> ProductVariant | None:
        """Возвращает цифровой вариант альбома."""
        product = getattr(album, 'product', None)
        if product is None:
            return None

        return product.variants.filter(is_active=True).order_by('id').first()

    def _get_carrier_variants(self, album) -> list[ProductVariant] | None:
        """Возвращает физические варианты альбома."""
        variants = []

        carriers = (
            Merch.objects
            .filter(album=album, is_carrier=True, is_active=True)
            .select_related('kind', 'product')
            .prefetch_related('product__variants', 'images_merch')
            .order_by('id')
        )

        for merch in carriers:
            product = getattr(merch, 'product', None)
            if product is None:
                continue

            variants.extend(
                product.variants
                .filter(is_active=True)
                .select_related(
                    'product',
                    'product__merch',
                    'product__merch__kind',
                )
                .order_by('id'),
            )

        return variants


class AlbumWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Album."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=True,
    )
    allow_overpay = serializers.BooleanField(required=False)

    class Meta:
        model = Album
        fields = (
            'name',
            'is_single',
            'release_date',
            'genre',
            'price',
            'description',
            'cover_image',
            'allow_overpay',
            'visibility',
            'is_published',
        )

    def validate_release_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                'Дата релиза не может быть в будущем.',
            )
        return value

    def create(self, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        return super().update(instance, validated_data)
