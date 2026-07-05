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

ALBUMS_TAGS = ['Albums']

album_schema = extend_schema_view(
    list=extend_schema(
        summary='Список альбомов',
        tags=ALBUMS_TAGS,
        description='Возвращает список альбомов.',
        parameters=[
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                description='Фильтр по slug жанра',
            ),
            OpenApiParameter(
                name='name',
                type=OpenApiTypes.STR,
                description='Поиск по названию',
            ),
            OpenApiParameter(
                name='artist',
                type=OpenApiTypes.STR,
                description='Фильтр по slug артиста',
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                description='Общий поиск (название, жанр)',
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                description=(
                    'Сортировка (name, -name, release_date, '
                    '-release_date, created_at, -created_at)'
                ),
            ),
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
    retrieve=extend_schema(
        summary='Получить альбом',
        tags=ALBUMS_TAGS,
        description='Возвращает альбом по id.',
    ),
    create=extend_schema(
        summary='Создать альбом',
        tags=ALBUMS_TAGS,
        description='Создаёт новый альбом.',
        responses={201: AlbumReadDetailSerializer},
    ),
    partial_update=extend_schema(
        summary='Частично обновить альбом',
        tags=ALBUMS_TAGS,
        description='Обновляет только переданные поля.',
        request=AlbumWriteSerializer,
        responses={200: AlbumReadDetailSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить альбом',
        tags=ALBUMS_TAGS,
        description='Удаляет альбом пользователя.',
    ),
)
