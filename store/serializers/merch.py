from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, PRICE_DECIMAL_PLACES
from store.models import Image, Merch, Product, ProductVariant
from store.serializers import ImageSerializer


class MerchReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Merch."""

    price = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Merch
        fields = (
            'id',
            'name',
            'description',
            'price',
            'main_image',
        )

    def get_price(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.price
        return None

    def get_main_image(self, obj):
        image = obj.images_merch.filter(is_main=True).first()
        if image:
            return image.image.url
        return None


class MerchDetailSerializer(MerchReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Merch."""

    allow_overpay = serializers.SerializerMethodField()
    images_merch = ImageSerializer(many=True, read_only=True)
    kind = serializers.StringRelatedField()
    album = serializers.StringRelatedField()

    class Meta(MerchReadSerializer.Meta):
        model = Merch
        fields = MerchReadSerializer.Meta.fields + (
            'allow_overpay',
            'images_merch',
            'kind',
            'album',
            'visibility',
            'is_published',
            'is_active',
        )

    def get_allow_overpay(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False


class MerchWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Merch."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        required=True,
        write_only=True,
    )
    allow_overpay = serializers.BooleanField(required=False)
    stock = serializers.IntegerField(required=False)
    images = ImageSerializer(many=True, write_only=True)

    class Meta:
        model = Merch
        fields = (
            'name',
            'kind',
            'price',
            'stock',
            'album',
            'description',
            'images',
            'allow_overpay',
            'visibility',
            'is_published',
            'is_active',
        )

    def validate_images(self, images):
        main_count = sum(1 for image in images if image.get('is_main'))
        if main_count > 1:
            raise serializers.ValidationError(
                'Только одно фото может быть главным.'
            )
        return images

    def to_representation(self, instance):
        return MerchDetailSerializer(instance).data

    def create(self, validated_data):

        price = validated_data.pop('price', None)
        allow_overpay = validated_data.pop('allow_overpay', False)
        stock = validated_data.pop('stock', 0)
        images = validated_data.pop('images')

        with transaction.atomic():
            merch = Merch.objects.create(**validated_data)

            for image in images:
                Image.objects.create(
                    merch=merch,
                    image=image['image'],
                    is_main=image.get('is_main', False),
                )

            product = Product.objects.create(
                merch=merch,
                price=(price if price is not None else Decimal('0.00')),
                allow_overpay=allow_overpay,
            )

            ProductVariant.objects.create(
                product=product,
                stock=stock,
                characteristic={'format': 'physical'},
            )

        return merch

    def update(self, instance, validated_data):

        price = validated_data.pop('price', None)
        allow_overpay = validated_data.pop('allow_overpay', None)
        stock = validated_data.pop('stock',  None)
        validated_data.pop('images', None)

        with transaction.atomic():

            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save(update_fields=[*validated_data.keys(), 'updated_at'])

            product, _ = Product.objects.get_or_create(merch=instance)

            if price is not None:
                product.price = price
            if allow_overpay is not None:
                product.allow_overpay = allow_overpay

            product.save()

            if stock is not None:
                ProductVariant.objects.filter(product=product).update(stock=stock)

        return instance
