"""Схемы OpenAPI для эндпоинтов аутентификации через внешний сервис."""

from drf_spectacular.utils import extend_schema

from users.serializers import SocialAuthInputSerializer, TokenPairSerializer

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

social_error_codes_schema = extend_schema(
    tags=['Auth'],
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
    tags=['Auth'],
    auth=[],
    summary='Аутентификация через внешнего провайдера',
    description=(
        'Принимает код (code) от провайдера и обменивает его на '
        'пару JWT-токенов. Если профиль соцсети ранее не был привязан '
        'к аккаунту, выполняется поиск по email '
        'или создание нового пользователя.'
    ),
    request=SocialAuthInputSerializer,
    responses={200: TokenPairSerializer},
)
