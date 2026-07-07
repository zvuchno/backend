"""Схемы автодокументации OpenAPI для расчета стоимости доставвок.

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
        'Принимает код города назначения и тип доставки. '
        'Группирует мерч в корзине по артистам, рассчитывает стоимость '
        'доставки для каждого плеча и возвращает суммарную стоимость.'
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
            },
        },
    },
    examples=[
        OpenApiExample(
            name='Успешный расчет',
            value={
                'delivery_sum': 450.00,
            },
            response_only=True,
        ),
    ],
    tags=DELIVERIES_TAGS,
)
