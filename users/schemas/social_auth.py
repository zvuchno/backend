"""Схемы OpenAPI для эндпоинтов аутентификации через внешний сервис."""

from drf_spectacular.utils import extend_schema

from users.serializers import (
    CookieLoginResponseSerializer,
    SocialAuthInputSerializer,
)

social_error_codes_schema = extend_schema(
    tags=['Auth: Social'],
    auth=[],
    summary='Справочник кодов ошибок social auth',
    description=(
        'Возвращает словарь кодов ошибок social auth и их '
        'базовых текстовых описаний. '
        'Фронтенд может использовать коды как контракт, а тексты — '
        'как fallback или для отладки.'
    ),
)

social_auth_schema = extend_schema(
    tags=['Auth: Social'],
    auth=[],
    summary=('Основной API endpoint для social auth через провайдера'),
    description=(
        'Основной способ social auth для новой интеграции фронтенда. '
        'Использовать эти endpoints вместо старого session exchange flow.\n\n'
        'Принимает code от провайдера и возвращает пару JWT-токенов. '
        'Если профиль соцсети ранее не был привязан к аккаунту, '
        'выполняется поиск по email или создание нового пользователя.\n\n'
        'VK OAuth может требовать альтернативный host из-за ограничений '
        'провайдера по разрешенным доменам. '
        'Yandex работает на основном dev-домене.\n\n'
        'Требует совместной проверки с фронтом и реальным OAuth flow.'
    ),
    request=SocialAuthInputSerializer,
    responses={200: CookieLoginResponseSerializer},
)
