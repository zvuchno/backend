"""Схемы автодокументации OpenAPI для глобального поиска каталога.

Содержит конфигурацию `drf-spectacular` для отображения
эндпоинта глобального поиска в Swagger/ReDoc.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from store.serializers import CatalogSearchSerializer

CATALOG_SEARCH_TAGS = ['Global Search']


catalog_search_schema = extend_schema(
    summary='Глобальный поиск по каталогу',
    description=(
        'Выполняет поиск по глобальному каталогу. '
        'Ищет артистов, альбомы, треки и мерч, '
        'в том числе по жанрам и типам мерча. '
        'Поддерживает полнотекстовый поиск и поиск '
        'с небольшими опечатками.'
    ),
    tags=CATALOG_SEARCH_TAGS,
    parameters=[
        OpenApiParameter(
            name='q',
            type=OpenApiTypes.STR,
            required=True,
            description='Поисковый запрос.',
        ),
    ],
    responses=CatalogSearchSerializer(many=True),
)
