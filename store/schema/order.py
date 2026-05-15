"""Схемы автодокументации OpenAPI для сущности Заказов.

Содержит конфигурации `drf-spectacular` для валидного отображения
операций управления заказами в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

from store.serializers.order import OrderDetailSerializer, OrderSerializer

ORDER_TAGS = ['Orders']

order_schema = extend_schema_view(
    list=extend_schema(
        summary='Список заказов',
        description='Возвращает список заказов пользователя.',
        responses={200: OrderSerializer},
        tags=ORDER_TAGS,
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                description=(
                    'Поиск по номеру заказа, названию товара или SKU '
                ),
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                description='Количество элементов в ответе',
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                description='Смещение от начала выборки',
            ),
        ],
    ),
    retrieve=extend_schema(
        summary='Получить заказ',
        description='Возвращает подробную информацию о заказе по id.',
        responses={200: OrderDetailSerializer},
        tags=ORDER_TAGS,
    ),
)
