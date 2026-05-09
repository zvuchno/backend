"""Схемы автодокументации OpenAPI для сущности Избранного.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

FAVORITES_TAGS = ['Favorites']

favorites_schema = extend_schema_view(
    list=extend_schema(
        summary='Список избранного текущего пользователя',
        description=(
            'Возвращает все объекты, добавленные '
            'текущим пользователем в избранное.',
        ),
        tags=FAVORITES_TAGS,
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                description='Количество элементов в ответе.',
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                description='Смещение от начала выборки.',
            ),
        ],
    ),
    create=extend_schema(
        summary='Добавить в избранное',
        description=(
            'Добавляет указанный продукт в список '
            'избранного текущего пользователя.',
        ),
        tags=FAVORITES_TAGS,
    ),
    destroy=extend_schema(
        summary='Удалить из избранного',
        description='Удаляет объект из списка избранного по его ID.',
        tags=FAVORITES_TAGS,
    ),
)
