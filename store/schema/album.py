"""Схемы автодокументации OpenAPI для сущности Альбомов.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

from store.serializers import (
    AlbumReadDetailSerializer,
    AlbumWriteSerializer,
)

album_schema = extend_schema_view(
    list=extend_schema(
        summary='Список альбомов',
        tags=['Album'],
        description='Возвращает список альбомов.',
        parameters=[
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Фильтр по ID жанра',
            ),
            OpenApiParameter(
                name='name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Поиск по названию',
            ),
            OpenApiParameter(
                name='artist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Фильтр по ID профиля артиста',
            ),
            OpenApiParameter(
                name='artist_name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Поиск по имени артиста',
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Общий поиск (название, описание, жанр)',
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Сортировка (name, release_date, created_at)',
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Количество элементов в ответе.',
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала выборки.',
            ),
        ],
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
