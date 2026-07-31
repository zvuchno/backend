"""OpenAPI-схемы настроек доставки управляемых профилей."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import (
    ArtistPickupPointManageSerializer,
    ArtistShippingPointSerializer,
)

artist_pickup_point_schema = extend_schema_view(
    list=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить точки самовывоза профиля',
        description=(
            'Возвращает точки самовывоза собственного или выбранного '
            'управляемого профиля.'
        ),
        responses=ArtistPickupPointManageSerializer(many=True),
    ),
    create=extend_schema(
        tags=['Artist: delivery'],
        summary='Добавить точку самовывоза профиля',
        description=(
            'Создаёт точку самовывоза для собственного или выбранного '
            'управляемого профиля.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses={
            201: ArtistPickupPointManageSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить точку самовывоза профиля',
        description=(
            'Возвращает конкретную точку самовывоза собственного или '
            'выбранного управляемого профиля.'
        ),
        responses=ArtistPickupPointManageSerializer,
    ),
    partial_update=extend_schema(
        tags=['Artist: delivery'],
        summary='Изменить точку самовывоза профиля',
        description=(
            'Частично обновляет точку самовывоза собственного или '
            'выбранного управляемого профиля.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses=ArtistPickupPointManageSerializer,
    ),
    destroy=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить точку самовывоза профиля',
        description=(
            'Удаляет точку самовывоза собственного или выбранного '
            'управляемого профиля.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)


artist_shipping_point_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить ПВЗ отправления профиля',
        description=(
            'Возвращает текущий ПВЗ СДЭК собственного или выбранного '
            'управляемого профиля. Если ПВЗ не настроен, возвращает null.'
        ),
        responses={
            200: ArtistShippingPointSerializer(allow_null=True),
        },
    ),
    put=extend_schema(
        tags=['Artist: delivery'],
        summary='Настроить ПВЗ отправления профиля',
        description=(
            'Создаёт или полностью заменяет ПВЗ СДЭК собственного или '
            'выбранного управляемого профиля. При создании возвращает '
            '201, при обновлении существующего ПВЗ — 200.'
        ),
        request=ArtistShippingPointSerializer,
        responses={
            200: ArtistShippingPointSerializer,
            201: ArtistShippingPointSerializer,
        },
    ),
    delete=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить ПВЗ отправления профиля',
        description=(
            'Удаляет текущий ПВЗ отправления собственного или выбранного '
            'управляемого профиля. Если ПВЗ отсутствует, операция также '
            'завершается успешно.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)
