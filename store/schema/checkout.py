"""Схемы автодокументации OpenAPI для чекаута заказа.

Содержит конфигурации `drf-spectacular` для валидного отображения
операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.serializers import (
    CheckoutSerializer,
    DeliverySerializer,
    OrderSerializer,
    PickupPointSerializer,
)

CHECKOUT_TAGS = ['Checkout']


def checkout_schema(view_func):
    """Декоратор для документирования экшена оформления заказа (GET и POST)."""
    return extend_schema(
        methods=['GET'],
        tags=CHECKOUT_TAGS,
        summary='Данные для оформления заказа',
        description=(
            'Возвращает дефолтные данные пользователя, '
            'сумму корзины и список доставок.',
        ),
        responses={
            200: inline_serializer(
                name='CheckoutInfoResponse',
                fields={
                    'user_defaults': inline_serializer(
                        name='UserDefaults',
                        fields={
                            'full_name': serializers.CharField(read_only=True),
                            'email': serializers.EmailField(read_only=True),
                            'phone': serializers.CharField(read_only=True),
                            'city': serializers.CharField(read_only=True),
                        },
                    ),
                    'subtotal': serializers.DecimalField(
                        max_digits=MAX_PRICE_DIGITS,
                        decimal_places=MONEY_DISPLAY_PRECISION,
                        help_text='Сумма товаров в корзине без учета доставки',
                    ),
                    'deliveries': DeliverySerializer(
                        many=True,
                        read_only=True,
                    ),
                    'pickup_points': PickupPointSerializer(
                        many=True,
                        read_only=True,
                    ),
                },
            ),
        },
    )(
        extend_schema(
            methods=['POST'],
            tags=CHECKOUT_TAGS,
            summary='Создание заказа',
            description='Валидирует данные и создает заказ на основе корзины.',
            request=CheckoutSerializer,
            responses={201: OrderSerializer},
        )(view_func),
    )
