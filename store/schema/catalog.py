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
        'Карточка строится на основе Product и может представлять альбом, '
        'сингл, носитель, обычный мерч или другой товарный тип.\n\n'
        'Поле detail содержит данные для перехода на detail-ручку:\n'
        '- type — тип detail-ручки, которую должен открыть фронт;\n'
        '- id — идентификатор объекта detail-ручки;\n'
        '- target_url — URL detail-ручки;\n'
        '- preselect_variant_id — вариант товара, который нужно '
        'предвыбрать на detail-странице.\n\n'
        'Например, карточка винила технически является merch-продуктом, '
        'но ведет на detail альбома и передает preselect_variant_id '
        'варианта винила.\n\n'
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
                'album',
                'merch',
            ],
            description=(
                'Фильтр по типу продукта. '
                'all — все товары, album — альбомы/синглы, '
                'merch — мерч и носители, если они хранятся как merch.'
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
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                'Поиск по названию товара и имени артиста. '
                'Набор полей зависит от реализации view.'
            ),
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
                'id': 1,
                'product_type': 'album',
                'name': 'Название релиза',
                'artist_name': 'Артист',
                'kind': 'Альбом',
                'year': 2026,
                'price': '500.00',
                'image': 'https://zvuchno.ru/media/albums/cover.jpg',
                'is_favorite': False,
                'detail': {
                    'type': 'album',
                    'id': 10,
                    'target_url': '/api/v1/store/albums/10/',
                    'preselect_variant_id': 101,
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Носитель',
            value={
                'id': 2,
                'product_type': 'merch',
                'name': 'Название релиза — винил',
                'artist_name': 'Артист',
                'kind': 'Винил',
                'year': None,
                'price': '2500.00',
                'image': 'https://zvuchno.ru/media/merch/vinyl.jpg',
                'is_favorite': False,
                'detail': {
                    'type': 'album',
                    'id': 10,
                    'target_url': '/api/v1/store/albums/10/',
                    'preselect_variant_id': 202,
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Обычный мерч',
            value={
                'id': 3,
                'product_type': 'merch',
                'name': 'Футболка',
                'artist_name': 'Артист',
                'kind': 'Футболка',
                'year': None,
                'price': '1500.00',
                'image': 'https://zvucho.ru/media/merch/tshirt.jpg',
                'is_favorite': False,
                'detail': {
                    'type': 'merch',
                    'id': 20,
                    'target_url': '/api/v1/store/merch/20/',
                },
            },
            response_only=True,
        ),
    ],
)
