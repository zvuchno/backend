"""Схемы автодокументации OpenAPI для виджета СДЭК."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
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
            'Используется для получения списка ПВЗ (action=offices) и расчета '
            'стоимости/сроков доставки (action=calculate). '
            'Для корректной работы виджета при запросе ПВЗ (action=offices) '
            'обязательно передавайте параметр "city".'
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
                name='city',
                type=OpenApiTypes.STR,
                description='Название города для поиска ПВЗ.',
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
