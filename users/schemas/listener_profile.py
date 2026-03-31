"""Схемы OpenAPI для эндпоинтов профиля слушателя."""

from drf_spectacular.utils import extend_schema, extend_schema_view

listener_me_schema = extend_schema_view(
    get=extend_schema(
        tags=['Listener'],
        summary='Получить свой профиль слушателя',
        description=(
            'Возвращает профиль слушателя, связанный с текущей '
            'авторизованной учетной записью.'
        ),
    ),
    patch=extend_schema(
        tags=['Listener'],
        summary='Обновить свой профиль слушателя',
        description=(
            'Частично обновляет профиль слушателя, связанный с текущей '
            'авторизованной учетной записью.'
        ),
    ),
)
