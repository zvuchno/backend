"""Схемы OpenAPI для эндпоинтов профиля артиста или лейбла."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

from users.serializers import ManagedArtistProfileSerializer

artist_cover_update_schema = extend_schema(
    tags=['Artists'],
    summary='Обновить обложку своего профиля',
    description=(
        'Загружает или заменяет обложку профиля текущего артиста '
        'или лейбла. Запрос должен быть отправлен '
        'в формате multipart/form-data.'
    ),
)

managed_artist_cover_update_schema = extend_schema(
    tags=['Artists'],
    summary='Обновить обложку управляемого профиля',
    description=(
        'Загружает или заменяет обложку выбранного профиля артиста '
        'или лейбла, доступного текущему пользователю. '
        'Запрос должен быть отправлен в формате multipart/form-data.'
    ),
)

artist_me_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artists'],
        summary='Получить свой профиль артиста или лейбла',
        description=(
            'Возвращает профиль артиста или лейбла '
            'текущего пользователя вместе '
            'с контактами и ссылками на внешние ресурсы.'
        ),
    ),
    patch=extend_schema(
        tags=['Artists'],
        summary='Обновить свой профиль артиста или лейбла',
        description=(
            'Частично обновляет профиль артиста или лейбла '
            'текущего пользователя. '
            'При передаче contacts и socials списки синхронизируются '
            'целиком: новые элементы создаются, существующие обновляются, '
            'а отсутствующие в запросе удаляются.'
        ),
    ),
)

artist_public_schema = extend_schema(
    tags=['Artists'],
    auth=[],
    summary='Получить публичный профиль артиста или лейбла',
    description=(
        'Возвращает публичные данные активного профиля артиста '
        'или лейбла по его slug.'
    ),
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
                'Сортировка. Например: name, -name, created_at, -created_at.'
            ),
        ),
    ],
)


label_managed_profile_list_schema = extend_schema(
    tags=['Label: managed profiles'],
    summary='Получить профили, доступные текущему лейблу',
    description=(
        'Возвращает профиль текущего лейбла и активные профили артистов, '
        'которыми он управляет. Профиль самого лейбла возвращается первым '
        'и помечается полем is_self=true.'
    ),
    responses={
        200: ManagedArtistProfileSerializer(many=True),
    },
)
