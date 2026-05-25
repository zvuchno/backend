"""Сериализаторы для работы с альбомами и их коммерческими данными.

Содержит классы для чтения и записи данных модели Album, включая
автоматическое создание связанных объектов Product и ProductVariant.
Используются в API для создания и обновления альбомов и их товарных данных.
"""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .genre import GenreSerializer
from .image import ImageSerializer
from store.constants import (
    CHAR_PRESET_DIGITAL,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import (
    Album,
    ProductVariant,
)


class AlbumReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Album."""

    price = serializers.SerializerMethodField()
    artist_name = serializers.CharField(
        source='owner.artist_profile.name',
        read_only=True,
    )

    class Meta:
        model = Album
        fields = (
            'id',
            'name',
            'artist_name',
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


class AlbumReadDetailSerializer(AlbumReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Album."""

    variants = serializers.SerializerMethodField()
    genre = GenreSerializer()
    images = serializers.SerializerMethodField()

    class Meta(AlbumReadSerializer.Meta):
        fields = (
            'id',
            'name',
            'artist_name',
            'price',
            'description',
            'images',
            'visibility',
            'is_published',
            'is_single',
            'genre',
            'release_date',
            'variants',
        )

    def get_images(self, obj):
        """Возвращает изображения альбома в формате галереи."""
        if not obj.cover_image:
            return []

        return ImageSerializer(
            [
                {
                    'image': obj.cover_image,
                    'is_main': True,
                },
            ],
            many=True,
            context=self.context,
        ).data

    def get_variants(self, obj):
        """Возвращает варианты покупки альбома."""
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

        return AlbumVariantSerializer(
            variants,
            many=True,
            context=self.context,
        ).data


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
