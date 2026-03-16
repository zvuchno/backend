"""Схемы автодокументации OpenAPI для сущности Жанров.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import GenreSerializer

genre_schema = extend_schema_view(
    list=extend_schema(
        summary='Список жанров',
        description='Возвращает список всех жанров.',
        tags=['Genres'],
    ),
    retrieve=extend_schema(
        summary='Получить жанр',
        description='Возвращает жанр по id.',
        tags=['Genres'],
    ),
    create=extend_schema(
        summary='Создать жанр',
        description='Создаёт новый жанр.',
        tags=['Genres'],
        request=GenreSerializer,
        responses={201: GenreSerializer},
    ),
    update=extend_schema(
        summary='Обновить жанр',
        tags=['Genres'],
        request=GenreSerializer,
        responses=GenreSerializer,
    ),
    partial_update=extend_schema(
        summary='Частично обновить жанр',
        tags=['Genres'],
        request=GenreSerializer,
        responses=GenreSerializer,
    ),
    destroy=extend_schema(
        summary='Удалить жанр',
        description='Удаляет жанр.',
        tags=['Genres'],
        responses={204: None},
    ),
)
