"""Сериализаторы для работы с корзиной покупателя.

Содержит классы для чтения и записи данных моделей Cart, CartItem.
"""

from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, PRICE_DECIMAL_PLACES
from store.models import Cart, CartItem, ProductVariant
from store.services.cart_service import CartService
from store.validators import validate_custom_price


class CartItemReadSerializer(serializers.ModelSerializer):
    """Сериализатор товаров в корзине пользователя - чтение."""

    product_variant = serializers.IntegerField(
        source='product_variant.id',
        read_only=True,
    )
    name = serializers.CharField(
        source='product_variant.variant_name',
        read_only=True,
    )
    price_with_donation = serializers.DecimalField(
        source='unit_price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        read_only=True,
    )
    stock = serializers.SerializerMethodField()
    line_total = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        read_only=True,
    )

    class Meta:
        model = CartItem
        fields = (
            'product_variant',
            'name',
            'price_with_donation',
            'quantity',
            'line_total',
            'comment',
            'stock',
        )

    def get_stock(self, obj) -> int:
        """Если цифра - наличие = 1."""
        variant = obj.product_variant
        if variant.product.product_type != 'merch':
            return 1
        return variant.stock

    def to_representation(self, instance):
        """Динамически скрывает custom_price, если переплата запрещена."""
        representation = super().to_representation(instance)
        # Проверяем флаг через связанный продукт
        if not instance.product_variant.product.allow_overpay:
            representation.pop('custom_price', None)
        return representation


class CartReadSerializer(serializers.ModelSerializer):
    """Сериализатор корзины покупок пользователя - чтение."""

    items = CartItemReadSerializer(
        many=True,
        read_only=True,
    )
    subtotal = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        read_only=True,
    )
    discounted_subtotal = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        read_only=True,
    )

    class Meta:
        model = Cart
        fields = ('items', 'subtotal', 'discounted_subtotal')


class CartItemWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи позиции в корзину."""

    product_variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
    )
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = CartItem
        fields = ('product_variant', 'quantity', 'custom_price', 'comment')

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
        # Проверка custom_price
        custom_price = attrs.get('custom_price')
        errors = validate_custom_price(product, custom_price)
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
