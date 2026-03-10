from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import AlbumReadSerializer, AlbumWriteSerializer


album_schema = extend_schema_view(
    list=extend_schema(
        summary='Список альбомов',
        tags=['Album'],
        description='Возвращает список альбомов.',
    ),
    retrieve=extend_schema(
        summary='Получить альбом',
        tags=['Album'],
        description='Возвращает альбом по id.',
    ),
    create=extend_schema(
        summary='Создать альбом',
        tags=['Album'],
        description='Создаёт новый альбом.',
        responses={201: AlbumReadSerializer},
    ),
    update=extend_schema(
        summary='Полностью обновить альбом',
        tags=['Album'],
        request=AlbumWriteSerializer,
        responses=AlbumReadSerializer,
    ),
    partial_update=extend_schema(
        summary='Частично обновить альбом',
        tags=['Album'],
        request=AlbumWriteSerializer,
        responses={200: AlbumReadSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить альбом',
        tags=['Album'],
        description='Удаляет альбом пользователя.',
    ),
)
