from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from store.serializers import ProductCatalogListSerializer

catalog_schema = extend_schema(
    tags=['Catalog'],
    auth=[],
    summary='Список товаров каталога',
    description=(
        'Возвращает публичный список товаров каталога. '
        'Поддерживает фильтрацию по типу товара.'
    ),
    parameters=[
        OpenApiParameter(
            name='type',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            enum=['all', 'album', 'merch'],
            description=(
                'Тип товара. all — все товары, album — альбомы, merch — мерч.'
            ),
        ),
    ],
    responses=ProductCatalogListSerializer(many=True),
)
