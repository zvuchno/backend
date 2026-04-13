"""Схемы автодокументации OpenAPI для модели корзины."""

from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

from store.serializers import (
    CartItemWriteSerializer,
    CartReadSerializer,
    CartWriteSerializer,
)

CART_TAGS = ['Cart']

cart_schema = extend_schema_view(
    me=[
        extend_schema(
            methods=['GET'],
            summary='Просмотр корзины',
            description=(
                'Возвращает состав корзины, итоговые суммы '
                'и примененный купон.'
            ),
            tags=CART_TAGS,
            responses={200: CartReadSerializer},
        ),
        extend_schema(
            methods=['PUT'],
            summary='Полная синхронизация корзины',
            description=(
                'Заменяет текущее содержимое корзины на '
                'присланный список товаров.'
            ),
            tags=CART_TAGS,
            request=CartWriteSerializer,
            responses={200: CartReadSerializer},
        ),
        extend_schema(
            methods=['PATCH'],
            summary='Частичное обновление корзины',
            description='Обновляет только переданные поля (например, купон).',
            tags=CART_TAGS,
            request=CartWriteSerializer,
            responses={200: CartReadSerializer},
        ),
    ],
    add_item=extend_schema(
        summary='Добавить товар',
        description='Добавляет один товар или увеличивает количество.',
        tags=CART_TAGS,
        request=CartItemWriteSerializer,
        responses={201: CartReadSerializer},
    ),
    remove_item=extend_schema(
        summary='Удалить товар',
        tags=CART_TAGS,
        parameters=[
            OpenApiParameter(
                name='variant_id',
                type=int,
                location=OpenApiParameter.PATH,
                required=True,
            ),
        ],
        responses={204: None},
    ),
)
