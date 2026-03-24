"""Сериализаторы для работы с альбомами и их коммерческими данными.

Содержит классы для чтения и записи данных модели Album, включая
автоматическое создание связанных объектов Product и ProductVariant.
Используются в API для создания и обновления альбомов и их товарных данных.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, PRICE_DECIMAL_PLACES
from store.models import Album, Product, ProductVariant


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
            'is_active',
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
            ret.pop('is_active', None)
            ret.pop('is_published', None)
        return ret


class AlbumReadDetailSerializer(AlbumReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Album."""

    allow_overpay = serializers.SerializerMethodField()

    class Meta(AlbumReadSerializer.Meta):
        fields = AlbumReadSerializer.Meta.fields + (
            'is_single',
            'genre',
            'release_date',
            'allow_overpay',
        )

    def get_allow_overpay(self, obj) -> bool:
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False


class AlbumWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Album."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
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
            'is_active',
        )

    def validate_release_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                'Дата релиза не может быть в будущем.',
            )
        return value

    def create(self, validated_data):
        """Создает Альбом и связанный Product."""
        price = validated_data.pop('price', None)
        allow_overpay = validated_data.pop('allow_overpay', False)

        with transaction.atomic():
            # Создаем Альбом
            album = Album.objects.create(**validated_data)

            # Создаем связанный Product
            product = Product.objects.create(
                album=album,
                price=(price if price is not None else Decimal('0.00')),
                allow_overpay=allow_overpay,
            )

            # Создаем базовый Вариант (Цифровая копия)
            ProductVariant.objects.create(
                product=product,
                stock=None,  # Для цифры склад не нужен
                characteristic={'format': 'digital'},
            )

        return album

    def update(self, instance, validated_data):
        """Обновляет Альбом и связанный Product."""
        price = validated_data.pop('price', None)
        allow_overpay = validated_data.pop('allow_overpay', None)

        with transaction.atomic():
            # Обновляем поля Альбома
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save(update_fields=validated_data.keys())

            # Получаем или создаем связанный Product
            product, created = Product.objects.get_or_create(album=instance)

            if price is not None:
                product.price = price
            if allow_overpay is not None:
                product.allow_overpay = allow_overpay

            product.save()

        return instance
