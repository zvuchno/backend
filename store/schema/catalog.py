from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from store.serializers import ProductCatalogListSerializer

catalog_schema = extend_schema(
    tags=['Catalog'],
    auth=[],
    summary='Список товаров каталога',
    description=(
        'Возвращает публичный список товаров каталога.\n\n'
        'Каталог строится от сущности Product и включает только товары, '
        'связанные с активным, опубликованным и публичным контентом.\n\n'
        'На текущем этапе каталог поддерживает альбомы и мерч. '
        'Треки в списке каталога не отображаются, они доступны внутри '
        'карточек альбомов.\n\n'
        'Фильтр genre применяется только к музыкальному контенту: '
        'альбомам и мерч-носителям, связанным с альбомом выбранного жанра. '
        'Обычный мерч без связи с альбомом при фильтрации по жанру '
        'в выдачу не попадает.'
    ),
    parameters=[
        OpenApiParameter(
            name='type',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            enum=['all', 'album', 'merch'],
            description=(
                'Тип товара. '
                'all — все товары, album — только альбомы, '
                'merch — только мерч. '
                'Если параметр не передан, возвращаются все доступные товары.'
            ),
        ),
        OpenApiParameter(
            name='genre',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            description=(
                'Slug жанра. '
                'Фильтрует альбомы и мерч-носители, связанные с альбомом '
                'выбранного жанра. Обычный мерч по жанру не фильтруется.'
            ),
        ),
        OpenApiParameter(
            name='limit',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Количество товаров в ответе.',
        ),
        OpenApiParameter(
            name='offset',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Смещение от начала списка.',
        ),
    ],
    responses=ProductCatalogListSerializer(many=True),
)
