"""Схемы автодокументации OpenAPI для сущности Промокодов.

Содержит конфигурации `drf-spectacular` для валидного отображения
CRUD-операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import PromocodeSerializer

PROMOCODE_FIELDS_DESCRIPTION = (
    'Поля промокода:\n'
    '- `code` - заглавные латинские буквы, цифры, дефис и подчёркивание;\n'
    '- `description` - необязательное описание;\n'
    '- `discount_type` - `PERCENT` (процент) или `FIXED` (рубли);\n'
    '- `discount_value` - для `PERCENT` 0.01-100, для `FIXED` от 0.01 руб;\n'
    '- `usage_limit` - максимум применений, `null` = без ограничения;\n'
    '- `start_at` - начало действия, `null` = сразу;\n'
    '- `end_at` - окончание, `null` = бессрочно;\n'
    '- `is_enabled` - видимость промокода для покупателей.'
)

PROMOCODES_TAGS = ['Promocodes']

promocode_schema = extend_schema_view(
    list=extend_schema(
        summary='Список промокодов',
        description='Возвращает промокоды текущего артиста.',
        responses={200: PromocodeSerializer},
        tags=PROMOCODES_TAGS,
    ),
    retrieve=extend_schema(
        summary='Получить промокод',
        description='Детальная информация о промокоде.',
        responses={200: PromocodeSerializer},
        tags=PROMOCODES_TAGS,
    ),
    create=extend_schema(
        summary='Создать промокод',
        description=(
            'Создаёт промокод от имени текущего артиста. '
            'Поле `owner` подставляется автоматически из аутентификации.\n\n'
            + PROMOCODE_FIELDS_DESCRIPTION
        ),
        responses={201: PromocodeSerializer},
        tags=PROMOCODES_TAGS,
    ),
    update=extend_schema(
        summary='Полностью обновить промокод',
        description=PROMOCODE_FIELDS_DESCRIPTION,
        responses={200: PromocodeSerializer},
        tags=PROMOCODES_TAGS,
    ),
    partial_update=extend_schema(
        summary='Частично обновить промокод',
        description=PROMOCODE_FIELDS_DESCRIPTION,
        responses={200: PromocodeSerializer},
        tags=PROMOCODES_TAGS,
    ),
    destroy=extend_schema(
        summary='Удалить промокод',
        description='Удаляет промокод.',
        responses={204: None},
        tags=PROMOCODES_TAGS,
    ),
)
