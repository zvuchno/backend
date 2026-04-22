"""Схемы автодокументации OpenAPI для сущности Жанров.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

genre_schema = extend_schema_view(
    list=extend_schema(
        summary='Список жанров',
        description='Возвращает список жанров.',
        tags=['Genres'],
    ),
)
