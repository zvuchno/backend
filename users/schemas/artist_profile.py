"""Схемы OpenAPI для эндпоинтов профиля артиста."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

artist_cover_update_schema = extend_schema(
    tags=['Artists'],
    summary='Обновить обложку своего профиля артиста',
    description=(
        'Загружает или заменяет обложку профиля текущего артиста. '
        'Запрос должен быть отправлен в формате multipart/form-data.'
    ),
)

artist_me_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artists'],
        summary='Получить свой профиль артиста',
        description=(
            'Возвращает профиль артиста текущего пользователя вместе '
            'с контактами и ссылками на внешние ресурсы.'
        ),
    ),
    patch=extend_schema(
        tags=['Artists'],
        summary='Обновить свой профиль артиста',
        description=(
            'Частично обновляет профиль артиста текущего пользователя. '
            'При передаче contacts и socials списки синхронизируются '
            'целиком: новые элементы создаются, существующие обновляются, '
            'а отсутствующие в запросе удаляются.'
        ),
    ),
)

artist_public_schema = extend_schema(
    tags=['Artists'],
    auth=[],
    summary='Получить публичный профиль артиста',
    description='Возвращает публичные данные активного артиста по его slug.',
)

artist_list_schema = extend_schema(
    tags=['Artists'],
    auth=[],
    summary='Получить список артистов',
    description=(
        'Возвращает публичный список активных артистов. '
        'Фильтр по жанру, поиск, пагинация.'
    ),
    parameters=[
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
        OpenApiParameter(
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Поиск по названию, slug, городу.',
        ),
        OpenApiParameter(
            name='genre',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Фильтр по жанру альбомов артиста.',
        ),
        OpenApiParameter(
            name='ordering',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                'Сортировка. Например: name, -name, created_at, -created_at.',
            ),
        ),
    ],
)
