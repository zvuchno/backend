"""Схемы автодокументации OpenAPI для финансовых отчетов артистов.

Содержит конфигурации `drf-spectacular` для отображения
операций получения отчетов в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

ARTIST_REPORTS_TAGS = ['Artist Reports']


artist_reports_schema = extend_schema_view(
    list=extend_schema(
        summary='Список финансовых отчетов артиста',
        description=(
            'Возвращает список сформированных финансовых отчетов '
            'текущего артиста с агрегированными данными о продажах '
            'за выбранные периоды.'
        ),
        tags=ARTIST_REPORTS_TAGS,
        parameters=[
            OpenApiParameter(
                name='period_type',
                type=OpenApiTypes.STR,
                description=(
                    'Тип периода отчета: daily — дневной, monthly — месячный.'
                ),
                required=False,
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                description=('Статус отчета: pending, ready, failed.'),
                required=False,
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                description='Количество элементов в ответе.',
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                description='Смещение от начала выборки.',
            ),
        ],
    ),
    retrieve=extend_schema(
        summary='Получить финансовый отчет артиста',
        description=(
            'Возвращает подробную информацию о финансовом отчете '
            'текущего артиста, включая агрегированные показатели '
            'продаж и ссылку на PDF-файл.'
        ),
        tags=ARTIST_REPORTS_TAGS,
    ),
)
