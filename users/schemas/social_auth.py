"""Схемы OpenAPI для эндпоинтов аутентификации через внешний сервис."""

from drf_spectacular.utils import extend_schema

from users.serializers import TokenPairSerializer

social_token_exchange_schema = extend_schema(
    tags=['Auth'],
    summary='Обмен social session на JWT токены. Не протестировано.',
    description=(
        'После успешной аутентификации через allauth и установки '
        'session cookie выполняет обмен текущей серверной сессии '
        'на access и refresh JWT токены.\n\n'
        'Точки входа в social auth flow:\n'
        '- /accounts/vk/login/\n'
        '- /accounts/yandex/login/\n\n'
        'VK OAuth может быть доступен только '
        'через альтернативный host из-за ограничений '
        'провайдера по разрешенным доменам. '
        'Yandex работает на основном dev-домене.\n\n'
        'Требует активной session cookie и CSRF токена.'
    ),
    responses={200: TokenPairSerializer},
)
