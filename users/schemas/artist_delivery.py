"""OpenAPI-схемы настроек доставки профилей артистов."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import (
    ArtistPickupPointManageSerializer,
    ArtistShippingPointSerializer,
)

artist_pickup_point_schema = extend_schema_view(
    list=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить свои точки самовывоза',
        description=(
            'Возвращает точки самовывоза профиля текущего артиста или лейбла.'
        ),
        responses=ArtistPickupPointManageSerializer(many=True),
    ),
    create=extend_schema(
        tags=['Artist: delivery'],
        summary='Добавить свою точку самовывоза',
        description=(
            'Создаёт точку самовывоза для профиля текущего артиста или лейбла.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses={
            201: ArtistPickupPointManageSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить свою точку самовывоза',
        description=(
            'Возвращает конкретную точку самовывоза профиля текущего '
            'артиста или лейбла.'
        ),
        responses=ArtistPickupPointManageSerializer,
    ),
    partial_update=extend_schema(
        tags=['Artist: delivery'],
        summary='Изменить свою точку самовывоза',
        description=(
            'Частично обновляет точку самовывоза профиля текущего '
            'артиста или лейбла.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses=ArtistPickupPointManageSerializer,
    ),
    destroy=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить свою точку самовывоза',
        description=(
            'Удаляет точку самовывоза профиля текущего артиста или лейбла.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)


managed_artist_pickup_point_schema = extend_schema_view(
    list=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить точки самовывоза управляемого профиля',
        description=(
            'Возвращает точки самовывоза выбранного управляемого '
            'профиля артиста или лейбла.'
        ),
        responses=ArtistPickupPointManageSerializer(many=True),
    ),
    create=extend_schema(
        tags=['Artist: delivery'],
        summary='Добавить точку самовывоза управляемому профилю',
        description=(
            'Создаёт точку самовывоза для выбранного управляемого '
            'профиля артиста или лейбла.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses={
            201: ArtistPickupPointManageSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить точку самовывоза управляемого профиля',
        description=(
            'Возвращает конкретную точку самовывоза выбранного '
            'управляемого профиля артиста или лейбла.'
        ),
        responses=ArtistPickupPointManageSerializer,
    ),
    partial_update=extend_schema(
        tags=['Artist: delivery'],
        summary='Изменить точку самовывоза управляемого профиля',
        description=(
            'Частично обновляет точку самовывоза выбранного '
            'управляемого профиля артиста или лейбла.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses=ArtistPickupPointManageSerializer,
    ),
    destroy=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить точку самовывоза управляемого профиля',
        description=(
            'Удаляет точку самовывоза выбранного управляемого '
            'профиля артиста или лейбла.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)


artist_shipping_point_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить свой ПВЗ отправления',
        description=(
            'Возвращает текущий ПВЗ СДЭК профиля текущего артиста '
            'или лейбла. Если ПВЗ не настроен, возвращает null.'
        ),
        responses={
            200: ArtistShippingPointSerializer(allow_null=True),
        },
    ),
    put=extend_schema(
        tags=['Artist: delivery'],
        summary='Настроить свой ПВЗ отправления',
        description=(
            'Создаёт или полностью заменяет ПВЗ СДЭК профиля текущего '
            'артиста или лейбла. При создании возвращает 201, при '
            'обновлении существующего ПВЗ — 200.'
        ),
        request=ArtistShippingPointSerializer,
        responses={
            200: ArtistShippingPointSerializer,
            201: ArtistShippingPointSerializer,
        },
    ),
    delete=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить свой ПВЗ отправления',
        description=(
            'Удаляет текущий ПВЗ отправления профиля текущего артиста '
            'или лейбла. Если ПВЗ отсутствует, операция также '
            'завершается успешно.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)


managed_artist_shipping_point_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить ПВЗ отправления управляемого профиля',
        description=(
            'Возвращает текущий ПВЗ СДЭК выбранного управляемого '
            'профиля артиста или лейбла. Если ПВЗ не настроен, '
            'возвращает null.'
        ),
        responses={
            200: ArtistShippingPointSerializer(allow_null=True),
        },
    ),
    put=extend_schema(
        tags=['Artist: delivery'],
        summary='Настроить ПВЗ отправления управляемого профиля',
        description=(
            'Создаёт или полностью заменяет ПВЗ СДЭК выбранного '
            'управляемого профиля артиста или лейбла. При создании '
            'возвращает 201, при обновлении существующего ПВЗ — 200.'
        ),
        request=ArtistShippingPointSerializer,
        responses={
            200: ArtistShippingPointSerializer,
            201: ArtistShippingPointSerializer,
        },
    ),
    delete=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить ПВЗ отправления управляемого профиля',
        description=(
            'Удаляет текущий ПВЗ отправления выбранного управляемого '
            'профиля артиста или лейбла. Если ПВЗ отсутствует, '
            'операция также завершается успешно.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)
