"""Схемы автодокументации OpenAPI для сущности Альбомов.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import (
    AlbumReadDetailSerializer,
    AlbumWriteSerializer,
)

album_schema = extend_schema_view(
    list=extend_schema(
        summary='Список альбомов',
        tags=['Album'],
        description='Возвращает список альбомов.',
    ),
    retrieve=extend_schema(
        summary='Получить альбом',
        tags=['Album'],
        description='Возвращает альбом по id.',
    ),
    create=extend_schema(
        summary='Создать альбом',
        tags=['Album'],
        description='Создаёт новый альбом.',
        responses={201: AlbumReadDetailSerializer},
    ),
    update=extend_schema(
        summary='Полностью обновить альбом',
        tags=['Album'],
        request=AlbumWriteSerializer,
        responses={200: AlbumReadDetailSerializer},
    ),
    partial_update=extend_schema(
        summary='Частично обновить альбом',
        tags=['Album'],
        request=AlbumWriteSerializer,
        responses={200: AlbumReadDetailSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить альбом',
        tags=['Album'],
        description='Удаляет альбом пользователя.',
    ),
)
