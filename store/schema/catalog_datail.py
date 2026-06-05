"""Схемы OpenAPI для детальных карточек каталога."""

from drf_spectacular.utils import OpenApiExample, extend_schema

from store.serializers.catalog_detail import (
    CatalogMerchDetailSerializer,
    CatalogReleaseDetailSerializer,
)

CATALOG_TAGS = ['Catalog']


catalog_release_detail_schema = extend_schema(
    tags=CATALOG_TAGS,
    auth=[],
    summary='Детальная карточка релиза в каталоге',
    description=(
        'Возвращает данные релиза для публичной витрины.\n\n'
        'В ответ входит сам релиз и список вариантов покупки: цифровой '
        'вариант и связанные носители.\n\n'
        'Поле property_name показывает название свойства, по которому '
        'выбирается вариант. Для релиза это формат.\n\n'
        'Если пользователь перешел из карточки носителя, фронтенд может '
        'сопоставить selected_variant_id из карточки каталога с variant_id '
        'одного из вариантов в этом ответе и сразу выбрать нужный вариант.\n\n'
        'Для добавления в корзину используется '
        'variant_id выбранного варианта.'
        'default_variant_id - для обозначения варианта по умолчанию'
        '(цифровая версия альбома).'
    ),
    responses=CatalogReleaseDetailSerializer,
    examples=[
        OpenApiExample(
            name='Релиз с цифровым вариантом и винилом',
            value={
                'id': 10,
                'name': 'Название релиза',
                'artist_name': 'Артист',
                'price': '500.00',
                'description': 'Описание релиза.',
                'images': [
                    {
                        'image': 'https://zvuchno.ru/media/albums/cover.jpg',
                        'is_main': True,
                    },
                ],
                'is_single': False,
                'genre': 'Rock',
                'release_date': '2026-06-01',
                'property_name': 'Формат',
                'variants': [
                    {
                        'value': 'Диджитал',
                        'name': 'Название релиза',
                        'id': 101,
                        'price': '500.00',
                        'stock': None,
                        'description': '',
                        'images': [
                            {
                                'image': (
                                    'https://zvuchno.ru/media/albums/cover.jpg'
                                ),
                                'is_main': True,
                            },
                        ],
                        'sku': 'ALB-10-V101',
                    },
                    {
                        'value': 'Винил',
                        'name': 'Название релиза — винил',
                        'id': 202,
                        'price': '2500.00',
                        'stock': 4,
                        'description': 'Описание винила.',
                        'images': [
                            {
                                'image': (
                                    'https://zvuchno.ru/media/merch/vinyl.jpg'
                                ),
                                'is_main': True,
                            },
                        ],
                        'sku': 'MER-20-V202',
                    },
                ],
            },
            response_only=True,
        ),
    ],
)


catalog_merch_detail_schema = extend_schema(
    tags=CATALOG_TAGS,
    auth=[],
    summary='Детальная карточка мерча в каталоге',
    description=(
        'Возвращает данные обычного мерча для публичной витрины.\n\n'
        'Носители здесь не отдаются. Носители доступны как варианты покупки '
        'в детальной карточке релиза.\n\n'
        'Поле property_name показывает название свойства, по которому '
        'выбирается вариант: например размер или цвет.\n\n'
        'Для добавления в корзину используется '
        'variants.id выбранного варианта.'
    ),
    responses=CatalogMerchDetailSerializer,
    examples=[
        OpenApiExample(
            name='Обычный мерч',
            value={
                'id': 20,
                'name': 'Футболка',
                'artist_name': 'Артист',
                'price': '1500.00',
                'description': 'Описание футболки.',
                'images': [
                    {
                        'image': 'https://zvuchno.ru/media/merch/tshirt.jpg',
                        'is_main': True,
                    },
                ],
                'kind': 'Футболка',
                'property_name': 'Размер',
                'stock': 7,
                'variants': [
                    {
                        'variant_id': 301,
                        'sku': 'MER-20-V301',
                        'stock': 3,
                        'value': 'M',
                    },
                    {
                        'variant_id': 302,
                        'sku': 'MER-20-V302',
                        'stock': 4,
                        'value': 'L',
                    },
                ],
            },
            response_only=True,
        ),
    ],
)
