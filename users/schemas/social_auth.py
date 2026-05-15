"""Схемы OpenAPI для эндпоинтов аутентификации через внешний сервис."""

from drf_spectacular.utils import extend_schema

from users.serializers import SocialAuthInputSerializer, TokenPairSerializer

social_token_exchange_schema = extend_schema(
    tags=['Auth'],
    summary='LEGACY: обмен server session на JWT токены',
    description=(
        'Старый session-based flow. '
        'Не стоит использовать для новой интеграции фронтенда.\n\n'
        'Работает только после успешной аутентификации через allauth '
        'и установки session cookie: endpoint обменивает текущую '
        'серверную сессию на access и refresh JWT токены.\n\n'
        'Точки входа в старый social auth flow:\n'
        '- /accounts/vk/login/\n'
        '- /accounts/yandex/login/\n\n'
        'VK OAuth может требовать альтернативный host из-за ограничений '
        'провайдера по разрешенным доменам. '
        'Yandex работает на основном dev-домене.\n\n'
        'Требует активной session cookie и CSRF токена.\n\n'
        'Для новой интеграции использовать API endpoints '
        '/api/v1/auth/social/vk/ и /api/v1/auth/social/yandex/.'
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
    responses={200: TokenPairSerializer},
)
