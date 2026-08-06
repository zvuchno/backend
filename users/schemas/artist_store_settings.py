"""Схемы OpenAPI для настроек магазина артиста или лейбла."""

from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import ArtistStoreSettingsSerializer

artist_store_settings_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artist: store settings'],
        summary='Получить настройки своего магазина',
        description=(
            'Возвращает собственные настройки магазина текущего артиста '
            'или лейбла. Если настройки ещё не созданы, возвращается null. '
            'Настройки управляющего лейбла в ответ не подставляются.'
        ),
        responses={
            200: ArtistStoreSettingsSerializer,
        },
    ),
    put=extend_schema(
        tags=['Artist: store settings'],
        summary='Сохранить настройки своего магазина',
        description=(
            'Создаёт или полностью обновляет собственные настройки магазина '
            'текущего артиста или лейбла. Пустая строка очищает '
            'соответствующее значение.'
        ),
        request=ArtistStoreSettingsSerializer,
        responses={
            200: ArtistStoreSettingsSerializer,
            201: ArtistStoreSettingsSerializer,
        },
    ),
)


managed_artist_store_settings_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artist: store settings'],
        summary='Получить настройки магазина управляемого профиля',
        description=(
            'Возвращает собственные настройки магазина выбранного профиля, '
            'доступного текущему лейблу. Если настройки ещё не созданы, '
            'возвращается null. Настройки лейбла в ответ не подставляются.'
        ),
        responses={
            200: ArtistStoreSettingsSerializer,
        },
    ),
    put=extend_schema(
        tags=['Artist: store settings'],
        summary='Сохранить настройки магазина управляемого профиля',
        description=(
            'Создаёт или полностью обновляет собственные настройки магазина '
            'выбранного управляемого профиля. Пустая строка очищает '
            'соответствующее значение.'
        ),
        request=ArtistStoreSettingsSerializer,
        responses={
            200: ArtistStoreSettingsSerializer,
            201: ArtistStoreSettingsSerializer,
        },
    ),
)
