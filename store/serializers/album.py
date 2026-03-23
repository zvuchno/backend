"""Сериализаторы для работы с альбомами и их коммерческими данными.

Содержит сериализаторы для чтения и записи данных модели Album, включая
управление связанными моделями Product, ProductVariant, Carrier.
Используются в API для создания и обновления альбомов и их товарных данных.
TODO: Если цена варианта носителя не передана - подставляем цену альбома
- выяснить у заказчика логику ценообразования носителя, реализовать её в коде.
"""

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .carrier import CarrierSerializer
from store.constants import MAX_PRICE_DIGITS, PRICE_DECIMAL_PLACES
from store.models import Album, Carrier, Product, ProductVariant


class AlbumReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Album."""

    base_price = serializers.SerializerMethodField()
    genre = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Album
        fields = (
            'id',
            'name',
            'is_single',
            'release_date',
            'genre',
            'base_price',
            'description',
            'cover_image',
            'visibility',
            'is_published',
            'is_active',
        )

    def get_base_price(self, obj) -> Decimal | None:
        product = getattr(obj, 'product', None)
        if product:
            return product.base_price
        return None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        user = self.context['request'].user

        # Скрываем поля, если юзер — не владелец и не админ
        if not (
            user.is_authenticated and (user == instance.owner or user.is_staff)
        ):
            ret.pop('visibility', None)
            ret.pop('is_active', None)
            ret.pop('is_published', None)
        return ret


class CarrierVariantSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения вариантов носителей в detail альбома."""

    carrier = CarrierSerializer(read_only=True)

    class Meta:
        model = ProductVariant
        fields = ('id', 'carrier', 'price', 'stock', 'sku')


class AlbumReadDetailSerializer(AlbumReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Album."""

    allow_overpay = serializers.SerializerMethodField()
    carriers = serializers.SerializerMethodField()

    class Meta(AlbumReadSerializer.Meta):
        fields = AlbumReadSerializer.Meta.fields + (
            'allow_overpay',
            'carriers',
        )

    @extend_schema_field(CarrierVariantSerializer(many=True))
    def get_carriers(self, obj):
        # Достаем продукт, связанный с этим альбомом
        product = getattr(obj, 'product', None)
        if not product:
            return []

        # Оптимизируем запрос, подтягивая данные носителя сразу
        variants = product.variants.select_related('carrier').all()
        return CarrierVariantSerializer(variants, many=True).data

    def get_allow_overpay(self, obj) -> bool:
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False


class CarrierQuantityPriceSerializer(serializers.Serializer):
    """Сериализатор для количества носителей альбома.

    Используется внутри AlbumWriteSerializer
    для создания/обновления ProductVariant.
    """

    id = serializers.PrimaryKeyRelatedField(queryset=Carrier.objects.all())
    stock = serializers.IntegerField(min_value=0, default=0)
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        required=False,
    )


class AlbumWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Album."""

    base_price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        required=True,
    )
    allow_overpay = serializers.BooleanField(required=False)
    carriers = CarrierQuantityPriceSerializer(many=True, required=False)

    class Meta:
        model = Album
        fields = (
            'name',
            'is_single',
            'release_date',
            'genre',
            'base_price',
            'description',
            'cover_image',
            'allow_overpay',
            'visibility',
            'is_published',
            'is_active',
            'carriers',
        )

    def validate_release_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                'Дата релиза не может быть в будущем.',
            )
        return value

    def create(self, validated_data):
        base_price = validated_data.pop('base_price', None)
        allow_overpay = validated_data.pop('allow_overpay', False)
        carriers_data = validated_data.pop('carriers', [])

        with transaction.atomic():
            # Создаем Альбом
            album = Album.objects.create(**validated_data)

            # Создаем Product
            product = Product.objects.create(
                album=album,
                base_price=(
                    base_price if base_price is not None else Decimal('0.00')
                ),
                allow_overpay=allow_overpay,
            )

            # Создаем варианты носителя с указанным количеством
            for item in carriers_data:
                # Product_variant требует уникальный SKU, а т.к. мы его пока
                # не передаем, то сгенерируем
                carrier = item['id']
                generated_sku = (
                    f'ALB-{album.id}-{carrier.name}'
                    f'-{uuid.uuid4().hex[:4]}'.upper()
                )
                ProductVariant.objects.create(
                    product=product,
                    carrier=item['id'],
                    stock=item['stock'],
                    # Пока берем цену носителя или base_price
                    price=item.get('price', base_price),
                    sku=generated_sku,
                )
            return album

    def update(self, instance, validated_data):
        base_price = validated_data.pop('base_price', None)
        allow_overpay = validated_data.pop('allow_overpay', None)
        carriers_data = validated_data.pop('carriers', [])

        with transaction.atomic():
            # Обновляем Album
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Обновляем Product
            product = instance.product

            if base_price is not None:
                product.base_price = base_price
            if allow_overpay is not None:
                product.allow_overpay = allow_overpay
            product.save()

            # Обновляем ProductVariant
            existing_variants = {
                pv.carrier_id: pv for pv in product.variants.all()
            }

            incoming_carriers = []

            for item in carriers_data:
                carrier = item['id']
                stock = item['stock']
                # Берем цену носителя, если нет - альбома, нет - сохраненную
                variant_price = item.get(
                    'price',
                    base_price
                    if base_price is not None
                    else product.base_price,
                )
                incoming_carriers.append(carrier.id)

                if carrier.id in existing_variants:
                    # Обновляем существующий
                    variant = existing_variants[carrier.id]
                    variant.stock = stock
                    variant.price = variant_price
                    variant.save()
                else:
                    # Создаем новый
                    generated_sku = (
                        f'ALB-{instance.id}-{carrier.name}'
                        f'-{uuid.uuid4().hex[:4]}'.upper()
                    )
                    ProductVariant.objects.create(
                        product=product,
                        carrier=carrier,
                        stock=stock,
                        price=variant_price,
                        sku=generated_sku,
                    )
            # Удаляем лишние
            for carrier_id, variant in existing_variants.items():
                if carrier_id not in incoming_carriers:
                    variant.delete()

        return instance
