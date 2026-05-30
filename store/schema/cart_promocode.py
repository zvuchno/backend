"""Схемы автодокументации OpenAPI для работы с промокодом в корзине.

Содержит конфигурации `drf-spectacular` для валидного отображения
операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status

from store.serializers import ApplyPromocodeSerializer, CartReadSerializer

CART_TAGS = ['Cart']


def cart_apply_promocode_schema(view_func):
    """Декоратор для документирования экшена применения промокода."""
    return extend_schema(
        methods=['POST'],
        summary='Применить промокод к корзине',
        description=(
            'Ищет активный промокод по переданному коду, привязывает '
            'его к текущей корзине и возвращает её обновленное состояние '
            'с учетом примененной скидки.'
        ),
        request=ApplyPromocodeSerializer,
        responses={
            status.HTTP_200_OK: CartReadSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description='Промокод не найден, истёк или '
                'не прошёл валидацию формата.',
                examples=[
                    OpenApiExample(
                        'Промокод не найден',
                        value={'error': 'Промокод не найден или неактивен'},
                        response_only=True,
                    ),
                ],
            ),
        },
        tags=CART_TAGS,
    )(view_func)


def cart_remove_promocode_schema(view_func):
    """Декоратор для документирования экшена удаления промокода."""
    return extend_schema(
        methods=['POST'],
        summary='Удалить промокод из корзины',
        description='Отвязывает промокод от текущей корзины '
        'и возвращает её актуальное состояние.',
        request=None,
        responses={
            status.HTTP_200_OK: CartReadSerializer,
        },
        tags=CART_TAGS,
    )(view_func)
