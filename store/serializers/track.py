"""Сериализаторы для работы с треками.

Содержит сериализаторы для чтения и записи данных модели Track,
используемые в API.
TODO: Реализовать логику покупки аудиофайла:
- ссылка на загрузку только купившему?
- в списке треков отдавать демку?
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, PRICE_DECIMAL_PLACES
from store.models import Product, ProductVariant, Track


class TrackReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Track."""

    price = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = (
            'id',
            'name',
            'album',
            'duration',
            'position',
            'price',
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
        # Скрываем поле, если юзера нет, если не владелец и не админ
        if not user or not (
            user.is_authenticated and (user == instance.owner or user.is_staff)
        ):
            ret.pop('is_active', None)
        return ret


class TrackReadDetailSerializer(TrackReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Track."""

    allow_overpay = serializers.SerializerMethodField()

    class Meta(TrackReadSerializer.Meta):
        fields = TrackReadSerializer.Meta.fields + (
            'audio_file',
            'allow_overpay',
            'description',
        )

    def get_allow_overpay(self, obj) -> bool:
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False


class TrackWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        required=True,
    )
    allow_overpay = serializers.BooleanField(required=False)

    class Meta:
        model = Track
        fields = (
            'name',
            'album',
            'audio_file',
            'position',
            'price',
            'allow_overpay',
            'description',
        )

    def create(self, validated_data):
        """Создает Трек и связанный Product."""
        price = validated_data.pop('price', None)
        allow_overpay = validated_data.pop('allow_overpay', False)

        with transaction.atomic():
            # Создаем Трек
            track = Track.objects.create(**validated_data)

            # Создаем связанный Product
            product = Product.objects.create(
                track=track,
                price=(price if price is not None else Decimal('0.00')),
                allow_overpay=allow_overpay,
            )

            # Создаем базовый Вариант (Цифровая копия)
            ProductVariant.objects.create(
                product=product,
                stock=None,  # Для цифры склад не нужен
                characteristic={'format': 'digital'},
            )

        return track

    def update(self, instance, validated_data):
        """Обновляет Трек и связанный Product."""
        price = validated_data.pop('price', None)
        allow_overpay = validated_data.pop('allow_overpay', None)

        with transaction.atomic():
            # Обновляем поля Трека
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save(update_fields=validated_data.keys())

            # Получаем или создаем связанный Product
            product, created = Product.objects.get_or_create(track=instance)

            if price is not None:
                product.price = price
            if allow_overpay is not None:
                product.allow_overpay = allow_overpay

            product.save()

        return instance
