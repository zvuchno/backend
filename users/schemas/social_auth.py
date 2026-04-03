"""Схемы OpenAPI для эндпоинтов аутентификации через внешний сервис."""

from drf_spectacular.utils import extend_schema

social_token_exchange_schema = extend_schema(
    tags=['Auth'],
    auth=[],
    summary='Получение токенов после аутентификации через соцсеть.',
    description='Подхватывает allauth сессию пользователя и выдает'
    ' access и refresh токены',
)
