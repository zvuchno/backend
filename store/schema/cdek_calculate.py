"""Схемы автодокументации OpenAPI для расчета стоимости доставок.

Содержит конфигурации `drf-spectacular` для валидного отображения
операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
)

from store.serializers import CdekCalculateSerializer

DELIVERIES_TAGS = ['Deliveries']


cdek_calculate_schema = extend_schema(
    summary='Расчет стоимости доставки СДЭК',
    description=(
        'Принимает код города назначения и метод доставки. '
        'Группирует мерч в корзине по артистам, рассчитывает стоимость и '
        'сроки доставки для каждого плеча. Возвращает суммарную стоимость и '
        'минимальный/максимальный сроки доставки среди всех отправлений.'
    ),
    request=CdekCalculateSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'delivery_sum': {
                    'type': 'number',
                    'format': 'float',
                    'description': 'Итоговая стоимость доставки в рублях',
                },
                'period_min': {
                    'type': 'integer',
                    'nullable': True,
                    'description': 'Минимальный срок доставки в днях '
                    '(с учетом худшего плеча)',
                },
                'period_max': {
                    'type': 'integer',
                    'nullable': True,
                    'description': 'Максимальный срок доставки в днях '
                    '(с учетом худшего плеча)',
                },
            },
        },
    },
    examples=[
        OpenApiExample(
            name='Успешный расчет',
            value={
                'delivery_sum': 450.00,
                'period_min': 2,
                'period_max': 5,
            },
            response_only=True,
        ),
    ],
    tags=DELIVERIES_TAGS,
)
