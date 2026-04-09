"""Схемы OpenAPI для эндпоинтов аутентификации через внешний сервис."""

from drf_spectacular.utils import extend_schema

social_token_exchange_schema = extend_schema(
    tags=['Auth'],
    summary='Обмен social session на JWT токены',
    description='После успешной аутентификации через allauth и установки '
    'session cookie выполняет обмен текущей серверной сессии '
    'на access и refresh JWT токены. '
    'Требует активной session cookie и CSRF токена.',
)
