"""Схемы OpenAPI для эндпоинтов аутентификации."""

from drf_spectacular.utils import extend_schema

from users.serializers.jwt import LogoutSerializer

token_obtain_schema = extend_schema(
    tags=['Auth'],
    auth=[],
    summary='Вход в систему',
    description='Аутентифицирует пользователя и возвращает access- и '
    'refresh-токены.',
)

token_refresh_schema = extend_schema(
    tags=['Auth'],
    auth=[],
    summary='Обновление access-токена',
    description='Возвращает новый access-токен '
    'по действующему refresh-токену.',
)

token_verify_schema = extend_schema(
    tags=['Auth'],
    auth=[],
    summary='Проверка токена',
    description='Проверяет корректность и срок действия переданного токена.',
)

logout_schema = extend_schema(
    tags=['Auth'],
    auth=[],
    request=LogoutSerializer,
    responses={204: None, 400: None},
    summary='Выход из системы',
    description=(
        'Инвалидирует refresh-токен пользователя, добавляя его в blacklist.'
    ),
)
