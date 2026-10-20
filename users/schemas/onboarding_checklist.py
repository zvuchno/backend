"""Схемы автодокументации OpenAPI для чек-листа онбординга.

Содержит конфигурации `drf-spectacular` для корректного отображения
эндпоинта чек-листа витрины в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

onboarding_checklist_schema = extend_schema_view(
    get=extend_schema(
        summary='Получить чек-лист онбординга витрины',
        description=(
            'Возвращает словарь со статусами выполнения шагов '
            'готовности витрины к продажам.'
        ),
        responses={
            200: inline_serializer(
                name='OnboardingChecklistResponse',
                fields={
                    'add_first_product': serializers.BooleanField(
                        help_text='Добавлен ли хотя бы один активный товар',
                    ),
                    'payout_details': serializers.BooleanField(
                        help_text='Заполнены ли реквизиты для выплат',
                    ),
                    'cdek_integration': serializers.BooleanField(
                        help_text='Настроена ли доставка СДЭК',
                    ),
                    'telegram_bot': serializers.BooleanField(
                        help_text='Подключен ли Telegram-бот для уведомлений',
                    ),
                    'publish_first_product': serializers.BooleanField(
                        help_text='Опубликован ли хотя бы один товар',
                    ),
                    'email_verified': serializers.BooleanField(
                        help_text='Подтверждён ли email учётной записи',
                    ),
                    'artist_cover': serializers.BooleanField(
                        help_text='Загружена ли обложка профиля',
                    ),
                },
            ),
        },
        tags=['Artists'],
        examples=[
            OpenApiExample(
                'Пример ответа',
                value={
                    'add_first_product': True,
                    'payout_details': False,
                    'cdek_integration': False,
                    'telegram_bot': False,
                    'publish_first_product': False,
                    'email_verified': True,
                    'artist_cover': True,
                },
                response_only=True,
            ),
        ],
    ),
)
