"""Схемы автодокументации OpenAPI для финансовых отчетов артистов.

Содержит конфигурации `drf-spectacular` для отображения
операций получения отчетов в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

ARTIST_REPORTS_TAGS = ['Reports']


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
                name='date_from',
                type=OpenApiTypes.DATE,
                description='Начало периода фильтрации.',
                examples=[
                    OpenApiExample(
                        'Пример',
                        value='2026-06-01',
                    ),
                ],
            ),
            OpenApiParameter(
                name='date_to',
                type=OpenApiTypes.DATE,
                description='Конец периода фильтрации.',
                examples=[
                    OpenApiExample(
                        'Пример',
                        value='2026-06-30',
                    ),
                ],
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                description='Количество элементов в ответе',
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                description='Смещение от начала выборки',
            ),
        ],
    ),
)
