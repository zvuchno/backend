"""Сериализаторы для работы с историей продаж артиста."""

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.serializers.order import OrderDetailSerializer, OrderSerializer


class ArtistSaleBaseMixin:
    """Миксин для общих полей продаж артиста."""

    @extend_schema_field(
        serializers.DecimalField(
            max_digits=MAX_PRICE_DIGITS,
            decimal_places=MONEY_DISPLAY_PRECISION,
        ),
    )
    def get_total(self, obj) -> Decimal:
        """Итоговая сумма товаров артиста в этом заказе."""
        return sum(item.line_total for item in obj.items.all())


class ArtistSaleSerializer(ArtistSaleBaseMixin, OrderSerializer):
    """Сериализтор заказа продавца."""

    total = serializers.SerializerMethodField()


class ArtistSaleDetailSerializer(ArtistSaleBaseMixin, OrderDetailSerializer):
    """Сериализтор для подробного просмотра заказа продавца."""

    total = serializers.SerializerMethodField()

    class Meta(OrderDetailSerializer.Meta):
        fields = tuple(
            field
            for field in OrderDetailSerializer.Meta.fields
            if field not in ('delivery_price', 'subtotal')
        )
