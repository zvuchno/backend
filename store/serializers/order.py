"""Сериализаторы для работы с заказом покупателя.

Содержит классы для чтения и записи данных моделей Order.
"""

from django.utils.dateparse import parse_date
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .base_variant_list_item import BaseVariantTargetImageSerializer
from .mixins import ProductImagesMixin
from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Delivery, Order, OrderItem


class OrderItemSerializer(BaseVariantTargetImageSerializer):
    """Сериализатор товаров в заказе."""

    sku = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    property_name = serializers.SerializerMethodField()
    property_value = serializers.SerializerMethodField()
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
    quantity = serializers.SerializerMethodField()

    class Meta(BaseVariantTargetImageSerializer.Meta):
        model = OrderItem
        fields = (
            'sku',
            'kind',
            'name',
            'property_name',
            'property_value',
            'price_at_purchase',
            'quantity',
            'donation',
            'promocode_discount',
            'line_total',
            'comment',
        ) + BaseVariantTargetImageSerializer.Meta.fields

    def get_sku(self, obj) -> str:
        return obj.product_info.get('sku') or ''

    def get_name(self, obj) -> str:
        return obj.product_info.get('name') or ''

    def get_kind(self, obj) -> str:
        return obj.product_info.get('kind') or ''

    def get_property_name(self, obj) -> str:
        return obj.product_info.get('property_name') or ''

    def get_property_value(self, obj) -> str:
        return obj.product_info.get('property_value') or ''

    def get_quantity(self, obj) -> str:
        if obj.product_info.get('product_type') in ['album', 'track']:
            return None
        return obj.quantity


class OrderSerializer(ProductImagesMixin, serializers.ModelSerializer):
    """Сериализтор заказа."""

    items_count = serializers.IntegerField(
        source='items_count_annotated',
        read_only=True,
    )
    total = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    images = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id',
            'order_number',
            'created_at',
            'status',
            'items_count',
            'total',
            'images',
        )

    @extend_schema_field(serializers.ListField(child=serializers.URLField()))
    def get_images(self, obj) -> list[str]:
        """Возвращает изображения товаров заказа."""
        urls = []
        for item in obj.items.all():
            product = item.product_variant.product
            if product.album_id:
                items = self.get_album_image_items(product.album)
            elif product.track_id:
                items = self.get_album_image_items(product.track.album)
            elif product.merch_id:
                items = self.get_merch_image_items(
                    product.merch.images_merch.all(),
                )
            else:
                continue

            url = self.get_main_image_url(items)
            if url:
                urls.append(url)

        return urls


class OrderDetailSerializer(OrderSerializer):
    """Сериализтор для подробного просмотра (retrieve) заказа."""

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
    delivery = serializers.CharField(
        source='delivery.name',
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
        if obj.delivery and obj.delivery.delivery_type == (
            Delivery.DeliveryType.ARTIST_PICKUP
        ):
            pickup = obj.pickup_point or {}

            address = pickup.get('address')
            date = pickup.get('date')

            if date:
                parsed_date = parse_date(date)
                if parsed_date:
                    date = parsed_date.strftime('%d.%m.%Y')

            return ', '.join(filter(None, (address, date)))

        parts = [
            f'г. {obj.city}' if obj.city else None,
            f'ул. {obj.street}' if obj.street else None,
            f'д. {obj.house}' if obj.house else None,
            f'кв/оф. {obj.apartment}' if obj.apartment else None,
        ]
        return ', '.join(filter(None, parts))
