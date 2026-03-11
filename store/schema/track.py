"""
Схемы автодокументации OpenAPI для сущности Треков.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import TrackSerializer


track_schema = extend_schema_view(
    list=extend_schema(
        summary='Список треков',
        tags=['Track'],
        description='Возвращает список всех аудиозаписей.',
    ),
    retrieve=extend_schema(
        summary='Получить трек',
        tags=['Track'],
        description='Возвращает детальную информацию о треке по id.',
    ),
    create=extend_schema(
        summary='Создать трек',
        tags=['Track'],
        description='Создаёт новую запись трека.',
        responses={201: TrackSerializer},
    ),
    update=extend_schema(
        summary='Полностью обновить трек',
        tags=['Track'],
        description='Обновляет все поля существующего трека.',
        responses={200: TrackSerializer},
    ),
    partial_update=extend_schema(
        summary='Частично обновить трек',
        tags=['Track'],
        description='Обновляет только переданные поля трека.',
        responses={200: TrackSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить трек',
        tags=['Track'],
        description='Удаляет запись трека.',
    ),
)
