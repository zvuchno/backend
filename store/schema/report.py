"""Схемы автодокументации для агентских отчетов артистов.

Содержит конфигурации `drf-spectacular` для отображения
операций получения и скачивания агентских отчетов
в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

ARTIST_REPORTS_TAGS = ['Reports']

artist_reports_schema = extend_schema_view(
    list=extend_schema(
        summary='Отчеты агента для артиста',
        description=(
            'Возвращает список сформированных агентских отчетов '
            'текущего артиста с агрегированными данными о продажах '
            'за отчетные периоды.'
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
                description='Количество элементов в ответе.',
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                description='Смещение от начала выборки.',
            ),
        ],
    ),
    download=extend_schema(
        summary='Скачать отчет агента ',
        description=('Возвращает PDF-файл отчета агента текущего артиста. '),
        tags=ARTIST_REPORTS_TAGS,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description='PDF-файл отчета агента.',
            ),
            404: OpenApiResponse(
                description='Отчет или файл отчета не найден.',
            ),
        },
    ),
)
