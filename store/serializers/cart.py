"""Сериализаторы для работы с корзиной покупателя.

Содержит классы для чтения и записи данных моделей Cart, CartItem.
"""

from rest_framework import serializers

from .mixins import ProductVariantURLMixin
from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Cart, CartItem, ProductVariant
from store.services.cart_service import CartService
from store.validators import validate_price_with_donation


class CartItemReadSerializer(
    ProductVariantURLMixin,
    serializers.ModelSerializer,
):
    """Сериализатор товаров в корзине пользователя - чтение."""

    product_variant = serializers.IntegerField(
        source='product_variant.id',
        read_only=True,
    )
    name = serializers.CharField(
        source='product_variant.variant_name',
        read_only=True,
    )
    price = serializers.DecimalField(
        source='unit_price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    stock = serializers.SerializerMethodField()
    line_total = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    target_url = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            'product_variant',
            'name',
            'price',
            'quantity',
            'line_total',
            'comment',
            'stock',
            'is_artist_subscription',
            'target_url',
        )

    def get_stock(self, obj) -> int:
        """Если цифра - наличие = 1."""
        variant = obj.product_variant
        product = variant.product
        if product.product_type != product.ProductType.MERCH:
            return 1
        return variant.stock


class CartReadSerializer(serializers.ModelSerializer):
    """Сериализатор корзины покупок пользователя - чтение."""

    items = CartItemReadSerializer(
        many=True,
        read_only=True,
    )
    subtotal = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    discount_promocode = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    total = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )

    class Meta:
        model = Cart
        fields = ('items', 'subtotal', 'discount_promocode', 'total')


class CartItemWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи позиции в корзину."""

    product_variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
    )
    quantity = serializers.IntegerField(min_value=1)
    is_artist_subscription = serializers.BooleanField(
        required=False,
        default=False,
    )

    class Meta:
        model = CartItem
        fields = (
            'product_variant',
            'quantity',
            'price_with_donation',
            'comment',
            'is_artist_subscription',
        )

    def validate(self, attrs):
        cart = self.context.get('cart')
        variant = attrs.get('product_variant')
        product = variant.product
        quantity = attrs.get('quantity')

        existing_item = cart.items.filter(product_variant=variant).first()

        view = self.context.get('view')
        is_adding = view and view.action == 'add_item'

        existing_qty = existing_item.quantity if existing_item else 0
        total_quantity = (existing_qty + quantity) if is_adding else quantity

        if product.product_type == 'track':
            track_obj = product.content
            # Если цена равна 0 - купить нельзя
            if track_obj and product.price == 0:
                raise serializers.ValidationError({
                    'product_variant': 'Этот трек нельзя приобрести '
                    'отдельно от альбома.',
                })

        if variant.product.product_type == 'merch':
            if variant.stock is not None and total_quantity > variant.stock:
                raise serializers.ValidationError({
                    'quantity': f'Недостаточно товара на складе. '
                    f'Доступно {variant.stock} шт.',
                })

        if product.product_type != 'merch' and total_quantity > 1:
            raise serializers.ValidationError({
                'quantity': 'Цифровой товар можно купить '
                'только в 1 экземпляре.',
            })
        # Проверка price_with_donation
        price_with_donation = attrs.get('price_with_donation')
        errors = validate_price_with_donation(product, price_with_donation)
        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class CartWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи корзины (PUT/PATCH)."""

    items = CartItemWriteSerializer(many=True, required=False)

    class Meta:
        model = Cart
        fields = ('items',)

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        instance = super().update(instance, validated_data)

        if items_data is not None:
            CartService.update_cart_items(
                cart=instance,
                items_data=items_data,
                partial=self.partial,
            )

        return instance
