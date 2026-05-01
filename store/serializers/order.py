"""Сериализаторы для работы с заказом покупателя.

Содержит классы для чтения и записи данных моделей Order.
"""

from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор товаров в заказе."""

    sku = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    donation = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    line_total = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    price_at_purchase = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    promocode_discount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )

    class Meta:
        model = OrderItem
        fields = (
            'id',
            'sku',
            'name',
            'price_at_purchase',
            'donation',
            'promocode_discount',
            'line_total',
            'comment',
        )

    def get_sku(self, obj) -> str:
        return obj.product_info.get('sku') or '-'

    def get_name(self, obj) -> str:
        return obj.product_info.get('name') or '-'


class OrderSerializer(serializers.ModelSerializer):
    """Сериализтор заказа."""

    items_count = serializers.IntegerField(
        source='items.count',
        read_only=True,
    )
    total = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )

    class Meta:
        model = Order
        fields = (
            'id',
            'order_number',
            'created_at',
            'status',
            'items_count',
            'total',
        )


class OrderDetailSerializer(OrderSerializer):
    """Сериализтор для подробного просмотра (retrieve) заказа."""

    status = serializers.CharField(source='get_status_display', read_only=True)
    full_address = serializers.SerializerMethodField()
    items = OrderItemSerializer(
        many=True,
        read_only=True,
    )
    subtotal = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    delivery_price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )

    class Meta:
        model = Order
        fields = (
            'id',
            'order_number',
            'created_at',
            'status',
            'full_name',
            'email',
            'phone',
            'delivery',
            'full_address',
            'items',
            'subtotal',
            'delivery_price',
            'total',
        )

    def get_full_address(self, obj) -> str:
        parts = [
            f'г. {obj.city}' if obj.city else None,
            f'ул. {obj.street}' if obj.street else None,
            f'д. {obj.house}' if obj.house else None,
            f'кв/оф. {obj.apartment}' if obj.apartment else None,
        ]
        return ', '.join(filter(None, parts))
