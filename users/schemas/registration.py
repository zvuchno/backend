"""Схемы OpenAPI для эндпоинтов регистрации пользователей."""

from drf_spectacular.utils import extend_schema

listener_registration_schema = extend_schema(
    tags=['Регистрация'],
    auth=[],
    summary='Регистрация слушателя',
    description=(
        'Создает учетную запись пользователя и связанный профиль слушателя.'
    ),
)

artist_registration_schema = extend_schema(
    tags=['Регистрация'],
    auth=[],
    summary='Регистрация артиста',
    description=(
        'Создает учетную запись пользователя, профиль слушателя '
        'и связанный профиль артиста.'
    ),
)
