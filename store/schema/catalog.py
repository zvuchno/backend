"""Схемы OpenAPI для каталога товаров."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
)

from store.serializers import CatalogCardSerializer

CATALOG_TAGS = ['Catalog']


catalog_list_schema = extend_schema(
    tags=CATALOG_TAGS,
    auth=[],
    summary='Список товаров каталога',
    description=(
        'Возвращает список товарных карточек каталога в едином формате.\n\n'
        'Карточка может представлять альбом, сингл, носитель или обычный '
        'мерч. Для перехода по клику фронтенд использует блок target.\n\n'
        'Важно: product_type показывает технический тип товара, а target '
        'показывает, какую detail-ручку нужно открыть. Например, винил '
        'технически является merch-товаром, '
        'но вести может на detail альбома.'
    ),
    parameters=[
        OpenApiParameter(
            name='limit',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Количество элементов в ответе.',
        ),
        OpenApiParameter(
            name='offset',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Смещение от начала выборки.',
        ),
        OpenApiParameter(
            name='type',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=[
                'all',
                'music',
                'merch',
            ],
            description=(
                'Фильтр по типу витрины. '
                'all — все товары каталога, '
                'music — музыкальные товары по макету, '
                'merch — мерч по макету.'
            ),
        ),
        OpenApiParameter(
            name='genre',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                'Фильтр по slug жанра. '
                'Применяется к альбомам и носителям, связанным с альбомом.'
            ),
        ),
        OpenApiParameter(
            name='artist',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Фильтр по slug артиста.',
        ),
        OpenApiParameter(
            name='ordering',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=[
                'created_at',
                '-created_at',
                'random',
            ],
            description=(
                'Сортировка товаров. '
                'created_at — сначала старые, '
                '-created_at или отсутствие параметра — сначала новые, '
                'random — случайный порядок.'
            ),
        ),
    ],
    responses=CatalogCardSerializer(many=True),
    examples=[
        OpenApiExample(
            name='Альбом',
            value={
                'product_type': 'album',
                'name': 'Название релиза',
                'artist_name': 'Артист',
                'kind': 'Альбом',
                'year': 2026,
                'price': '500.00',
                'image': 'https://zvuchno.ru/media/albums/cover.jpg',
                'is_favorite': False,
                'target': {
                    'type': 'album',
                    'id': 10,
                    'url': '/api/v1/store/albums/10/',
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Носитель',
            value={
                'product_type': 'merch',
                'name': 'Название релиза — винил',
                'artist_name': 'Артист',
                'kind': 'Винил',
                'year': None,
                'price': '2500.00',
                'image': 'https://zvuchno.ru/media/merch/vinyl.jpg',
                'is_favorite': False,
                'target': {
                    'type': 'album',
                    'id': 10,
                    'url': '/api/v1/store/albums/10/',
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Обычный мерч',
            value={
                'product_type': 'merch',
                'name': 'Футболка',
                'artist_name': 'Артист',
                'kind': 'Футболка',
                'year': None,
                'price': '1500.00',
                'image': 'https://zvuchno.ru/media/merch/tshirt.jpg',
                'is_favorite': False,
                'target': {
                    'type': 'merch',
                    'id': 20,
                    'url': '/api/v1/store/merch/20/',
                },
            },
            response_only=True,
        ),
    ],
)
