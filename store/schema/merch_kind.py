"""Схемы автодокументации OpenAPI для сущности типов мерча.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

merch_kinds_schema = extend_schema_view(
    list=extend_schema(
        summary='Типы мерча',
        description='Возвращает список типов мерча.',
        tags=['Merch kinds'],
    ),
)
