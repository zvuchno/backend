"""Схемы автодокументации OpenAPI для виджета СДЭК."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

CDEK_TAGS = ['Deliveries']

cdek_widget_schema = extend_schema_view(
    get=extend_schema(
        summary='Прокси для виджета СДЭК',
        description=(
            'Прокси-эндпоинт для работы виджета СДЭК v3.0.\n\n'
            'Используется для получения списка ПВЗ (action=offices).\n\n'
            'Для корректной работы виджета при запросе ПВЗ (action=offices) '
            'обязательно передавайте параметр "city_code".'
        ),
        tags=CDEK_TAGS,
        parameters=[
            OpenApiParameter(
                name='action',
                type=OpenApiTypes.STR,
                description='Действие (для получения офисов "offices").',
                required=True,
            ),
            OpenApiParameter(
                name='city_code',
                type=OpenApiTypes.STR,
                description='Код города в СДЭК для поиска ПВЗ.',
                required=True,
            ),
            OpenApiParameter(
                name='is_handout',
                type=OpenApiTypes.BOOL,
                description='Фильтр: наличие выдачи заказов.',
            ),
            OpenApiParameter(
                name='is_reception',
                type=OpenApiTypes.BOOL,
                description='Фильтр: наличие приема заказов.',
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Номер страницы (начинается с 0).',
            ),
            OpenApiParameter(
                name='size',
                type=OpenApiTypes.INT,
                description='Количество элементов на странице.',
            ),
        ],
        responses={
            200: inline_serializer(
                name='CDEKWidgetResponse',
                fields={
                    'points': serializers.ListField(
                        child=serializers.DictField(allow_empty=True),
                    ),
                    'page': serializers.IntegerField(),
                    'size': serializers.IntegerField(),
                    'total_elements': serializers.IntegerField(),
                    'total_pages': serializers.IntegerField(),
                },
            ),
        },
    ),
)


cdek_cities_suggest_schema = extend_schema(
    summary='Подсказки городов (автокомплит) через СДЭК',
    description=(
        'Принимает поисковую строку (минимум 2 символа) в query-параметре и '
        'возвращает список подходящих населенных пунктов из базы СДЭК. '
        'Используется для динамического автокомплита на фронтенде.'
    ),
    parameters=[
        OpenApiParameter(
            name='query',
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Поисковый запрос (название города или первые буквы)',
        ),
    ],
    responses={
        200: {
            'type': 'array',
            'description': 'Список найденных городов и регионов',
            'items': {
                'type': 'object',
                'properties': {
                    'city_uuid': {
                        'type': 'string',
                        'format': 'uuid',
                        'description': 'Уникальный идентификатор '
                        'города в СДЭК',
                    },
                    'code': {
                        'type': 'integer',
                        'description': 'Код города в СДЭК '
                        '(используется для расчета доставки)',
                    },
                    'full_name': {
                        'type': 'string',
                        'description': 'Полное название населенного пункта '
                        'с регионом и страной',
                    },
                    'country_code': {
                        'type': 'string',
                        'description': 'Двухбуквенный код страны '
                        '(например, RU)',
                    },
                },
            },
        },
    },
    examples=[
        OpenApiExample(
            name='Успешный поиск',
            value=[
                {
                    'city_uuid': '35da643b-b56c-4a70-af07-e125a4458193',
                    'code': 288,
                    'full_name': 'Владивосток, Владивостокский городской '
                    'округ, Приморский край, Россия',
                    'country_code': 'RU',
                },
                {
                    'city_uuid': '770f3275-921b-4552-a856-a16697d45691',
                    'code': 538682,
                    'full_name': 'Владивосток, департамент Луар и Шер, '
                    'Центр-Долина Луары, Франция',
                    'country_code': 'FR',
                },
            ],
            response_only=True,
        ),
    ],
    tags=CDEK_TAGS,
)
