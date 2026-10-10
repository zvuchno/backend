"""Схемы автодокументации OpenAPI для сущности Бонусов.

Содержит конфигурации `drf-spectacular` для отображения
операций создания, просмотра, изменения и удаления бонусов.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

from store.serializers import BonusReadSerializer, BonusReorderSerializer

BONUSES_TAGS = ['Bonuses']

bonus_schema = extend_schema_view(
    list=extend_schema(
        summary='Список бонусов',
        description='Возвращает бонусы, доступные текущему пользователю.',
        tags=BONUSES_TAGS,
        parameters=[
            OpenApiParameter(
                name='album',
                type=OpenApiTypes.INT,
                description='ID альбома для фильтрации бонусов.',
            ),
        ],
    ),
    retrieve=extend_schema(
        summary='Получение бонуса',
        description='Возвращает подробную информацию о бонусе.',
        tags=BONUSES_TAGS,
    ),
    create=extend_schema(
        summary='Создание бонуса',
        description='Создаёт бонус в альбоме артиста.',
        tags=BONUSES_TAGS,
    ),
    partial_update=extend_schema(
        summary='Изменение бонуса',
        description='Изменяет указанные поля бонуса.',
        tags=BONUSES_TAGS,
    ),
    destroy=extend_schema(
        summary='Удаление бонуса',
        description='Мягко удаляет бонус.',
        tags=BONUSES_TAGS,
    ),
)


def bonus_reorder_schema(view_func):
    """Декоратор для документирования экшена изменения порядка бонусов."""
    return extend_schema(
        methods=['PATCH'],
        summary='Изменить порядок бонусов',
        description=(
            'Изменяет порядок всех активных бонусов указанного альбома. '
            'Необходимо передать ID альбома и полный список ID его '
            'бонусов в требуемом порядке.'
        ),
        request=BonusReorderSerializer,
        responses={
            200: BonusReadSerializer(many=True),
        },
        tags=BONUSES_TAGS,
        filters=False,
    )(view_func)
