"""Схемы автодокументации OpenAPI для сущности Платежей.

Содержит конфигурации `drf-spectacular` для валидного отображения
инициализации платежей в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status

payment_schema = extend_schema_view(
    post=extend_schema(
        summary='Инициализация платежа',
        description=(
            'Инициирует создание платежа в ЮKassa для указанного '
            'заказа и возвращает URL для оплаты.',
        ),
        tags=['Payments'],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'order_id': {
                        'type': 'integer',
                        'description': 'Идентификатор заказа',
                    },
                },
                'required': ['order_id'],
            },
        },
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                description='Платеж успешно инициирован',
                response={
                    'type': 'object',
                    'properties': {
                        'confirmation_url': {
                            'type': 'string',
                            'format': 'uri',
                        },
                    },
                },
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description='Заказ не найден',
                response={
                    'type': 'object',
                    'properties': {'error': {'type': 'string'}},
                },
            ),
        },
        examples=[
            OpenApiExample(
                'Успешный ответ',
                value={
                    'confirmation_url': 'https://yoomoney.ru/checkout/payments/v2/contract?orderId=...',
                },
                response_only=True,
                status_codes=[str(status.HTTP_201_CREATED)],
            ),
        ],
    ),
)
