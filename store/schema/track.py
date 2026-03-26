"""Схемы автодокументации OpenAPI для сущности Треков."""

from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import (
    TrackReadDetailSerializer,
    TrackReadSerializer,
    TrackWriteSerializer,
)

track_schema = extend_schema_view(
    list=extend_schema(
        summary='Список треков',
        tags=['Track'],
        description='Возвращает список всех аудиозаписей.',
        responses={200: TrackReadSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary='Получить трек',
        tags=['Track'],
        description='Возвращает детальную информацию о треке по id.',
        responses={200: TrackReadDetailSerializer},
    ),
    create=extend_schema(
        summary='Загрузить трек',
        tags=['Track'],
        description='Создаёт новую запись трека.',
        request=TrackWriteSerializer,
        responses={201: TrackReadDetailSerializer},
    ),
    partial_update=extend_schema(
        summary='Частично обновить трек',
        tags=['Track'],
        description='Обновляет только переданные поля трека.',
        request=TrackWriteSerializer,
        responses={200: TrackReadDetailSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить трек',
        tags=['Track'],
        description='Удаляет запись трека.',
    ),
)
