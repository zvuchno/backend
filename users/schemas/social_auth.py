"""Схемы OpenAPI для эндпоинтов аутентификации."""

from drf_spectacular.utils import extend_schema

social_signup_schema = extend_schema(
    tags=['Auth'],
    auth=[],
    summary='Вход через VK.',
    description='Аутентифицирует пользователя через VK и возвращает access- и '
    'refresh-токены.',
)

social_complete_signup_schema = extend_schema(
    tags=['Auth'],
    auth=[],
    summary='Завершение регистрации через VK.',
    description='Запрашивает email для создания учетной записи и'
    'возвращает access- и refresh-токены.',
)
