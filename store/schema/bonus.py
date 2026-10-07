"""Схемы автодокументации OpenAPI для сущности Бонусов.

Содержит конфигурации `drf-spectacular` для отображения
операций создания, просмотра, изменения и удаления бонусов.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status

from store.constants import ALLOWED_BONUS_EXTENSIONS, MAX_BONUSFILE_SIZE_MB

bonus_schema = extend_schema_view(
    list=extend_schema(
        summary='Список бонусов',
        description='Возвращает бонусы, доступные текущему пользователю',
        parameters=[
            OpenApiParameter(
                name='album',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='ID альбома для фильтрации бонусов',
            ),
        ],
        tags=['Bonuses'],
    ),
    retrieve=extend_schema(
        summary='Получение бонуса',
        description='Возвращает подробную информацию о бонусе',
        tags=['Bonuses'],
    ),
    create=extend_schema(
        summary='Создание бонуса',
        description='Создаёт бонус в альбоме артиста',
        tags=['Bonuses'],
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Название бонуса',
                    },
                    'bonus_file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': (
                            'Файл бонуса ('
                            f'{
                                ", ".join(
                                    ext.upper()
                                    for ext in ALLOWED_BONUS_EXTENSIONS
                                )
                            }'
                            f'). Максимальный размер '
                            f'— {MAX_BONUSFILE_SIZE_MB} МБ.'
                        ),
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Описание бонуса',
                    },
                    'album': {
                        'type': 'integer',
                        'description': 'ID альбома',
                    },
                },
                'required': ['name', 'bonus_file', 'album'],
            },
        },
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                description='Бонус успешно создан',
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description='Некорректные данные бонуса',
            ),
        },
    ),
    partial_update=extend_schema(
        summary='Изменение бонуса',
        description='Изменяет указанные поля бонуса',
        tags=['Bonuses'],
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Название бонуса',
                    },
                    'bonus_file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Новый файл бонуса',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Описание бонуса',
                    },
                },
            },
        },
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description='Бонус успешно изменён',
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description='Некорректные данные бонуса',
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description='Бонус не найден',
            ),
        },
    ),
    destroy=extend_schema(
        summary='Удаление бонуса',
        description='Мягко удаляет бонус',
        tags=['Bonuses'],
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description='Бонус успешно удалён',
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description='Бонус не найден',
            ),
        },
    ),
)
