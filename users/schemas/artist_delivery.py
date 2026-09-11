"""OpenAPI-схемы настроек доставки профилей артистов."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import (
    ArtistPickupSettingsSerializer,
    ArtistShippingSettingsSerializer,
)

artist_pickup_point_schema = extend_schema_view(
    list=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить настройки самовывоза',
        description=(
            'Возвращает общее состояние самовывоза и точки '
            'профиля текущего артиста или лейбла.'
        ),
        responses=ArtistPickupSettingsSerializer,
    ),
    create=extend_schema(
        tags=['Artist: delivery'],
        summary='Сохранить настройки самовывоза',
        description=(
            'Одним запросом сохраняет состояние самовывоза '
            'и переданные изменения точек профиля текущего '
            'артиста или лейбла. В points можно передавать '
            'новые точки и изменённые поля существующих точек.'
        ),
        request=ArtistPickupSettingsSerializer,
        responses={
            200: ArtistPickupSettingsSerializer,
        },
    ),
)


managed_artist_pickup_point_schema = extend_schema_view(
    list=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить настройки самовывоза управляемого профиля',
        description=(
            'Возвращает общее состояние самовывоза и точки '
            'выбранного управляемого профиля.'
        ),
        responses=ArtistPickupSettingsSerializer,
    ),
    create=extend_schema(
        tags=['Artist: delivery'],
        summary='Сохранить настройки самовывоза управляемого профиля',
        description=(
            'Одним запросом сохраняет состояние самовывоза '
            'и переданные изменения точек выбранного '
            'управляемого профиля.'
        ),
        request=ArtistPickupSettingsSerializer,
        responses={
            200: ArtistPickupSettingsSerializer,
        },
    ),
)


artist_shipping_point_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить настройки доставки СДЭК',
        description=(
            'Возвращает состояние доставки СДЭК и сохранённый ПВЗ '
            'профиля текущего артиста или лейбла.'
        ),
        responses={
            200: ArtistShippingSettingsSerializer,
        },
    ),
    put=extend_schema(
        tags=['Artist: delivery'],
        summary='Сохранить настройки доставки СДЭК',
        description=(
            'Одним запросом сохраняет состояние доставки СДЭК '
            'и, если передан point, создаёт или обновляет ПВЗ '
            'профиля текущего артиста или лейбла.'
        ),
        request=ArtistShippingSettingsSerializer,
        responses={
            200: ArtistShippingSettingsSerializer,
        },
    ),
    delete=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить свой ПВЗ отправления',
        description=(
            'Удаляет ПВЗ СДЭК профиля текущего артиста или лейбла '
            'и автоматически выключает собственную доставку СДЭК. '
            'Если ПВЗ отсутствует, операция также завершается успешно.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)


managed_artist_shipping_point_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artist: delivery'],
        summary='Получить настройки СДЭК управляемого профиля',
        description=(
            'Возвращает состояние доставки СДЭК и сохранённый ПВЗ '
            'выбранного управляемого профиля.'
        ),
        responses={
            200: ArtistShippingSettingsSerializer,
        },
    ),
    put=extend_schema(
        tags=['Artist: delivery'],
        summary='Сохранить настройки СДЭК управляемого профиля',
        description=(
            'Одним запросом сохраняет состояние доставки СДЭК '
            'и, если передан point, создаёт или обновляет ПВЗ '
            'выбранного управляемого профиля.'
        ),
        request=ArtistShippingSettingsSerializer,
        responses={
            200: ArtistShippingSettingsSerializer,
        },
    ),
    delete=extend_schema(
        tags=['Artist: delivery'],
        summary='Удалить ПВЗ СДЭК управляемого профиля',
        description=(
            'Удаляет ПВЗ выбранного управляемого профиля '
            'и автоматически выключает его собственную доставку СДЭК. '
            'Если ПВЗ отсутствует, операция также завершается успешно.'
        ),
        responses={
            204: OpenApiTypes.NONE,
        },
    ),
)
