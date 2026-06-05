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
        'Поле default_variant_id содержит ID цифрового варианта, который '
        'можно выбрать по умолчанию при открытии карточки релиза.\n\n'
        'Если пользователь перешёл из карточки носителя, фронтенд может '
        'сопоставить selected_variant_id из карточки каталога с variant_id '
        'одного из вариантов в этом ответе '
        'и сразу выбрать нужный вариант.\n\n'
        'Для добавления в корзину используется '
        'variant_id выбранного варианта.'
    ),
    responses=CatalogReleaseDetailSerializer,
    examples=[
        OpenApiExample(
            name='Релиз с цифровым вариантом и винилом',
            value={
                'id': 10,
                'name': 'Название релиза',
                'price': '500.00',
                'description': 'Описание релиза.',
                'visibility': 'public',
                'is_published': True,
                'artist_name': 'Артист',
                'is_single': False,
                'genre': 'Rock',
                'release_date': '2026-06-01',
                'allow_overpay': False,
                'default_variant_id': 101,
                'images': [
                    {
                        'image': 'https://zvuchno.ru/media/albums/cover.jpg',
                        'is_main': True,
                    },
                ],
                'property_name': 'Формат',
                'variants': [
                    {
                        'variant_id': 101,
                        'sku': 'ALB-10-V101',
                        'stock': None,
                        'property_value': 'Диджитал',
                        'name': 'Название релиза',
                        'price': '500.00',
                        'description': 'Описание релиза.',
                        'images': [
                            {
                                'image': (
                                    'https://zvuchno.ru/media/albums/cover.jpg'
                                ),
                                'is_main': True,
                            },
                        ],
                    },
                    {
                        'variant_id': 202,
                        'sku': 'MER-20-V202',
                        'stock': 4,
                        'property_value': 'Винил',
                        'name': 'Название релиза — винил',
                        'price': '2500.00',
                        'description': 'Описание винила.',
                        'images': [
                            {
                                'image': (
                                    'https://zvuchno.ru/media/merch/vinyl.jpg'
                                ),
                                'is_main': True,
                            },
                        ],
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
        'Для добавления в корзину используется variant_id выбранного варианта.'
    ),
    responses=CatalogMerchDetailSerializer,
    examples=[
        OpenApiExample(
            name='Обычный мерч',
            value={
                'id': 20,
                'name': 'Футболка',
                'price': '1500.00',
                'description': 'Описание футболки.',
                'visibility': 'public',
                'is_published': True,
                'artist_name': 'Артист',
                'kind': 'Футболка',
                'album': None,
                'property_name': 'Размер',
                'stock': 7,
                'allow_overpay': False,
                'images': [
                    {
                        'image': 'https://zvuchno.ru/media/merch/tshirt.jpg',
                        'is_main': True,
                    },
                ],
                'variants': [
                    {
                        'variant_id': 301,
                        'sku': 'MER-20-V301',
                        'stock': 3,
                        'property_value': 'M',
                    },
                    {
                        'variant_id': 302,
                        'sku': 'MER-20-V302',
                        'stock': 4,
                        'property_value': 'L',
                    },
                ],
            },
            response_only=True,
        ),
    ],
)
