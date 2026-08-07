"""Схемы OpenAPI для экспорта продаж артиста.

Содержит конфигурацию `drf-spectacular` для отображения
CSV-экспорта продаж в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)

SALES_EXPORT_TAGS = ['Artist: sales']


sales_export_schema = extend_schema(
    summary='Выгрузить детализацию продаж артиста',
    description=(
        'Возвращает CSV-файл с детализированной информацией '
        'о продажах артиста за указанный период. '
    ),
    tags=SALES_EXPORT_TAGS,
    parameters=[
        OpenApiParameter(
            name='period_start',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            required=True,
            description=(
                'Дата начала периода в формате YYYY-MM-DD. '
                'Например: 2026-07-01.'
            ),
        ),
        OpenApiParameter(
            name='period_end',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            required=True,
            description=(
                'Дата окончания периода в формате YYYY-MM-DD. '
                'Например: 2026-07-31.'
            ),
        ),
    ],
    responses={
        200: {
            'description': 'CSV-файл.',
        },
    },
)
