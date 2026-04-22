"""Схемы автодокументации OpenAPI для сущности Треков."""

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)

from store.serializers import (
    TrackReadDetailSerializer,
    TrackReadSerializer,
    TrackWriteSerializer,
)

TRACKS_TAGS = ['Tracks']

track_schema = extend_schema_view(
    list=extend_schema(
        summary='Список треков',
        tags=TRACKS_TAGS,
        description='Возвращает список всех аудиозаписей.',
        parameters=[
            OpenApiParameter(
                name='name',
                type=OpenApiTypes.STR,
                description='Фильтр по названию трека (icontains)',
            ),
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.INT,
                description='Фильтр по ID жанра',
            ),
            OpenApiParameter(
                name='album',
                type=OpenApiTypes.INT,
                description='Фильтр по ID альбома',
            ),
            OpenApiParameter(
                name='artist_id',
                type=OpenApiTypes.INT,
                description='Фильтр по ID артиста',
            ),
            OpenApiParameter(
                name='artist_name',
                type=OpenApiTypes.STR,
                description='Фильтр по имени артиста (icontains)',
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                description='Поиск по названию',
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                description='Сортировка: position, -position, name, -name',
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Количество элементов в ответе.',
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала выборки.',
            ),
        ],
        responses={200: TrackReadSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary='Получить трек',
        tags=TRACKS_TAGS,
        description='Возвращает детальную информацию о треке по id.',
        responses={200: TrackReadDetailSerializer},
    ),
    create=extend_schema(
        summary='Загрузить трек',
        tags=TRACKS_TAGS,
        description='Создаёт новую запись трека.',
        request=TrackWriteSerializer,
        responses={201: TrackReadDetailSerializer},
    ),
    partial_update=extend_schema(
        summary='Частично обновить трек',
        tags=TRACKS_TAGS,
        description='Обновляет только переданные поля трека.',
        request=TrackWriteSerializer,
        responses={200: TrackReadDetailSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить трек',
        tags=TRACKS_TAGS,
        description='Удаляет запись трека.',
    ),
)
