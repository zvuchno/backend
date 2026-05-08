"""Сериализаторы для работы с заказом покупателя.

Содержит классы для чтения и записи данных моделей Order.
"""

from rest_framework import serializers

from .mixins import ProductVariantURLMixin
from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Order, OrderItem


class OrderItemSerializer(ProductVariantURLMixin, serializers.ModelSerializer):
    """Сериализатор товаров в заказе."""

    sku = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
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
    image = serializers.SerializerMethodField()
    target_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            'sku',
            'name',
            'property_name',
            'property_value',
            'price_at_purchase',
            'quantity',
            'donation',
            'promocode_discount',
            'line_total',
            'comment',
            'image',
            'target_url',
        )

    def get_sku(self, obj) -> str:
        return obj.product_info.get('sku') or ''

    def get_name(self, obj) -> str:
        return obj.product_info.get('name') or ''

    def get_property_name(self, obj) -> str:
        return obj.product_info.get('property_name') or ''

    def get_property_value(self, obj) -> str:
        return obj.product_info.get('property_value') or ''

    def get_image(self, obj) -> str:
        """Отдаем одну картинку в придачу для отображения позиции."""
        product = obj.product_variant.product
        product_type = product.product_type

        relative_url = None

        if product_type in (
            product.ProductType.ALBUM,
            product.ProductType.TRACK,
        ):
            if product_type == product.ProductType.ALBUM:
                album = getattr(product, 'album', None)
            else:
                track = getattr(product, 'track', None)
                album = getattr(track, 'album', None) if track else None

            if album and album.cover_image:
                relative_url = album.cover_image.url

        elif product_type == product.ProductType.MERCH:
            merch = getattr(product, 'merch', None)
            if merch:
                image_obj = merch.images_merch.all().first()
                if image_obj and image_obj.image:
                    relative_url = image_obj.image.url
        request = (
            self.context.get('request') if hasattr(self, 'context') else None
        )
        if relative_url and request:
            return request.build_absolute_uri(relative_url)

        return relative_url


class OrderSerializer(serializers.ModelSerializer):
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
