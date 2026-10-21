"""Схемы автодокументации OpenAPI для данных карты сайта.

Содержит конфигурации `drf-spectacular` для валидного отображения
эндпоинта sitemap в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
)

from common.seo.serializers import SitemapEntrySerializer

sitemap_schema = extend_schema_view(
    get=extend_schema(
        summary='Данные для карты сайта',
        description=(
            'Возвращает единый список публичных страниц (релизы, мерч, артисты'
            ') с датой последнего изменения. Используется '
            'фронтендом для сборки `sitemap.xml`.'
        ),
        responses=SitemapEntrySerializer(many=True),
        examples=[
            OpenApiExample(
                'Пример ответа',
                value=[
                    {
                        'type': 'release',
                        'id': 7,
                        'slug': None,
                        'lastmod': '2026-10-17T12:00:00Z',
                    },
                    {
                        'type': 'merch',
                        'id': 3,
                        'slug': None,
                        'lastmod': '2026-10-15T09:30:00Z',
                    },
                    {
                        'type': 'artist',
                        'id': None,
                        'slug': 'some-artist',
                        'lastmod': '2026-10-14T08:00:00Z',
                    },
                ],
                response_only=True,
            ),
        ],
        tags=['SEO'],
    ),
)
