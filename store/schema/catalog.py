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
        'Возвращает список витринных карточек товаров.\n\n'
        'Карточка может представлять релиз, носитель или обычный мерч. '
        'Для перехода по клику фронтенд использует target.url.\n\n'
        'target показывает, какую детальную карточку нужно открыть. '
        'Например, карточка носителя может вести на детальную карточку '
        'релиза.\n\n'
        'Если карточка должна открыть детальную карточку с заранее выбранным '
        'вариантом, фронтенд может использовать selected_variant_id для '
        'сопоставления с variant_id в детальной карточке.\n\n'
        'selected_variant_id может быть null. Например, для обычного мерча '
        'вариант может выбираться уже на детальной карточке.\n\n'
        'Поле is_favorite показывает, добавлен ли товар в избранное. '
        'Сейчас избранное связано с вариантом товара, поэтому карточка '
        'считается избранной, если в избранном есть любой вариант этого '
        'товара.'
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
                'Тип витрины. '
                'all или отсутствие параметра — релизы, носители и мерч; '
                'album — музыкальные релизы; '
                'merch — мерч и физические носители.'
            ),
        ),
        OpenApiParameter(
            name='genre',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                'Фильтр по slug жанров. Можно передать несколько значений '
                'через запятую: genre=rock,jazz. '
                'Применяется к релизам и носителям, связанным с релизом.'
            ),
        ),
        OpenApiParameter(
            name='kind',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                'Фильтр по slug типов мерча. Можно передать несколько '
                'значений через запятую: kind=vinyl,tshirt. '
                'Применяется к мерчу и носителям.'
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
                'created_at — сначала старые; '
                '-created_at или отсутствие параметра — сначала новые; '
                'random — случайный порядок.'
            ),
        ),
        OpenApiParameter(
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Поиск по названию товара и имени артиста.',
        ),
    ],
    responses=CatalogCardSerializer(many=True),
    examples=[
        OpenApiExample(
            name='Релиз',
            value={
                'name': 'Название релиза',
                'artist_name': 'Артист',
                'kind': 'Альбом',
                'year': 2026,
                'price': '500.00',
                'image': 'https://zvuchno.ru/media/albums/cover.jpg',
                'is_favorite': False,
                'target': {
                    'type': 'release',
                    'url': '/api/v1/store/catalog/release/10/',
                    'selected_variant_id': 111,
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Носитель',
            value={
                'name': 'Название релиза — винил',
                'artist_name': 'Артист',
                'kind': 'Винил',
                'year': None,
                'price': '2500.00',
                'image': 'https://zvuchno.ru/media/merch/vinyl.jpg',
                'is_favorite': False,
                'target': {
                    'type': 'release',
                    'url': '/api/v1/store/catalog/release/10/',
                    'selected_variant_id': 112,
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Обычный мерч',
            value={
                'name': 'Футболка',
                'artist_name': 'Артист',
                'kind': 'Футболка',
                'year': None,
                'price': '1500.00',
                'image': 'https://zvuchno.ru/media/merch/tshirt.jpg',
                'is_favorite': False,
                'target': {
                    'type': 'merch',
                    'url': '/api/v1/store/catalog/merch/20/',
                    'selected_variant_id': None,
                },
            },
            response_only=True,
        ),
    ],
)
