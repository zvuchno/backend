from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

ORDER_TAGS = ['Artists']

telegram_connect_schema = extend_schema_view(
    post=extend_schema(
        summary='Подключение Telegram для артиста',
        description=(
            'Генерирует одноразовую ссылку для подключения Telegram-бота '
            'и привязывает артиста после /start.'
        ),
        tags=ORDER_TAGS,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string'},
                    'connected': {'type': 'boolean'},
                },
            },
        },
    ),
)
