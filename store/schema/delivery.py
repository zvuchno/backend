"""Схемы автодокументации OpenAPI для сущности Доставок.

Содержит конфигурации `drf-spectacular` для валидного отображения
операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

delivery_schema = extend_schema_view(
    list=extend_schema(
        summary='Варианты доставки',
        description='Возвращает список вариантов доставки.',
        tags=['Deliveries'],
    ),
)
