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

from store.serializers import (
    ArtistSaleDetailSerializer,
    ArtistSaleSerializer,
)

ORDER_TAGS = ['Artists']

artist_sale_schema = extend_schema_view(
    list=extend_schema(
        summary='Получить список заказов',
        description='Возвращает список заказов для продавца.',
        responses={200: ArtistSaleSerializer},
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
        description='Возвращает подробную информацию '
        'о заказе для продавца по id.',
        responses={200: ArtistSaleDetailSerializer},
        tags=ORDER_TAGS,
    ),
)
