from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

catalog_schema = extend_schema(
    summary='Каталог',
    tags=['Catalog'],
    parameters=[
        OpenApiParameter(
            name='type',
            type=OpenApiTypes.STR,
            enum=['all', 'album', 'carrier', 'merch'],
            location=OpenApiParameter.QUERY,
            description='Тип выдачи каталога.',
        ),
        OpenApiParameter(
            name='offset',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Смещение пачки каталога.',
        ),
        OpenApiParameter(
            name='ordering',
            type=OpenApiTypes.STR,
            enum=['-created_at', 'created_at', 'random'],
            location=OpenApiParameter.QUERY,
            description='Сортировка.',
        ),
    ],
)
