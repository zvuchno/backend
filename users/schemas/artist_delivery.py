"""OpenAPI-схемы настроек доставки управляемых профилей."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import (
    ArtistPickupPointManageSerializer,
    ArtistShippingPointSerializer,
)

artist_pickup_point_schema = extend_schema_view(
    list=extend_schema(
        tags=['Artists'],
        summary='Получить точки самовывоза профиля',
        description=(
            'Возвращает точки самовывоза выбранного профиля артиста '
            'или лейбла, доступного текущему пользователю для управления.'
        ),
        responses=ArtistPickupPointManageSerializer(many=True),
    ),
    create=extend_schema(
        tags=['Artists'],
        summary='Добавить точку самовывоза профиля',
        description=(
            'Создаёт точку самовывоза для выбранного управляемого профиля.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses={
            201: ArtistPickupPointManageSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=['Artists'],
        summary='Получить точку самовывоза профиля',
        description=(
            'Возвращает конкретную точку самовывоза выбранного '
            'управляемого профиля.'
        ),
        responses=ArtistPickupPointManageSerializer,
    ),
    partial_update=extend_schema(
        tags=['Artists'],
        summary='Изменить точку самовывоза профиля',
        description=(
            'Частично обновляет точку самовывоза выбранного '
            'управляемого профиля.'
        ),
        request=ArtistPickupPointManageSerializer,
        responses=ArtistPickupPointManageSerializer,
    ),
    destroy=extend_schema(
        tags=['Artists'],
        summary='Удалить точку самовывоза профиля',
        description=(
            'Удаляет точку самовывоза выбранного управляемого профиля.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)


artist_shipping_point_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artists'],
        summary='Получить ПВЗ отправления профиля',
        description=(
            'Возвращает текущий ПВЗ СДЭК, из которого выбранный профиль '
            'отправляет заказы. Если ПВЗ не настроен, возвращает null.'
        ),
        responses={
            200: ArtistShippingPointSerializer(allow_null=True),
        },
    ),
    put=extend_schema(
        tags=['Artists'],
        summary='Настроить ПВЗ отправления профиля',
        description=(
            'Создаёт или полностью заменяет ПВЗ СДЭК для выбранного '
            'управляемого профиля. При создании возвращает 201, '
            'при обновлении существующего ПВЗ — 200.'
        ),
        request=ArtistShippingPointSerializer,
        responses={
            200: ArtistShippingPointSerializer,
            201: ArtistShippingPointSerializer,
        },
    ),
    delete=extend_schema(
        tags=['Artists'],
        summary='Удалить ПВЗ отправления профиля',
        description=(
            'Удаляет текущий ПВЗ отправления выбранного управляемого '
            'профиля. Если ПВЗ отсутствует, операция также завершается '
            'успешно.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)
