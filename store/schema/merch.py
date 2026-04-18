"""Схемы автодокументации OpenAPI для сущности Мерча.

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
    MerchDetailSerializer,
    MerchWriteSerializer,
)

merch_schema = extend_schema_view(
    list=extend_schema(
        summary='Список мерча',
        tags=['Merch'],
        description='Возвращает список мерча.',
        parameters=[
            OpenApiParameter(
                name='name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Поиск по названию',
            ),
            OpenApiParameter(
                name='kind',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Фильтр по типу мерча',
            ),
            OpenApiParameter(
                name='album',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Фильтр по ID альбома',
            ),
            OpenApiParameter(
                name='artist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Фильтр по ID артиста',
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
                description='Общий поиск (название, описание)',
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Сортировка (name, created_at)',
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
        summary='Получить мерч',
        tags=['Merch'],
        description='Возвращает мерч по id.',
    ),
    create=extend_schema(
        summary='Создать мерч',
        tags=['Merch'],
        description='Создаёт новый мерч.',
        request=MerchWriteSerializer,
        responses={201: MerchDetailSerializer},
    ),
    partial_update=extend_schema(
        summary='Частично обновить мерч',
        tags=['Merch'],
        description='Обновляет поля мерча. '
        'Картинки обновляются через отдельные эндпоинты.',
        request=MerchWriteSerializer,
        responses={200: MerchDetailSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить мерч',
        tags=['Merch'],
        description='Удаляет мерч.',
    ),
)
