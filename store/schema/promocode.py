"""Схемы автодокументации OpenAPI для сущности Промокодов.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import (
    PromocodeReadDetailSerializer,
    PromocodeReadSerializer,
)

PROMOCODES_TAGS = ['Promocodes']

promocode_schema = extend_schema_view(
    list=extend_schema(
        summary='Список промокодов',
        description='Возвращает промокоды текущего артиста.',
        responses={200: PromocodeReadSerializer},
        tags=PROMOCODES_TAGS,
    ),
    retrieve=extend_schema(
        summary='Получить промокод',
        description='Детальная информация о промокоде.',
        responses={200: PromocodeReadDetailSerializer},
        tags=PROMOCODES_TAGS,
    ),
    create=extend_schema(
        summary='Создать промокод',
        description=('Создаёт промокод от имени текущего артиста. '),
        responses={201: PromocodeReadDetailSerializer},
        tags=PROMOCODES_TAGS,
    ),
    partial_update=extend_schema(
        summary='Частично обновить промокод',
        description='Обновляет только переданные поля.',
        responses={200: PromocodeReadDetailSerializer},
        tags=PROMOCODES_TAGS,
    ),
    destroy=extend_schema(
        summary='Удалить промокод',
        description='Удаляет промокод.',
        responses={204: None},
        tags=PROMOCODES_TAGS,
    ),
)
