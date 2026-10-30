"""Схемы автодокументации OpenAPI для сущности Треков."""

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)

from store.serializers import (
    TrackPlacementCreateSerializer,
    TrackReadDetailSerializer,
    TrackReadSerializer,
    TrackReorderSerializer,
    TrackWriteSerializer,
)

TRACKS_TAGS = ['Tracks']

track_schema = extend_schema_view(
    list=extend_schema(
        summary='Список треков',
        tags=TRACKS_TAGS,
        description=(
            'Возвращает размещения мастер-записей в релизах. '
            'ID элемента — это ID ReleaseTrack, а не Recording.'
        ),
        parameters=[
            OpenApiParameter(
                name='name',
                type=OpenApiTypes.STR,
                description='Фильтр по названию трека (icontains)',
            ),
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                description='Фильтр по slug жанра',
            ),
            OpenApiParameter(
                name='album',
                type=OpenApiTypes.INT,
                description='Фильтр по ID альбома',
            ),
            OpenApiParameter(
                name='artist',
                type=OpenApiTypes.STR,
                description='Фильтр по slug артиста',
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
        description=(
            'Возвращает детальную информацию о ReleaseTrack по его ID. '
            'Название, описание, длительность и аудиофайл берутся '
            'из связанной Recording.'
        ),
        responses={200: TrackReadDetailSerializer},
    ),
    create=extend_schema(
        summary='Загрузить трек простым способом',
        tags=TRACKS_TAGS,
        description=(
            'Создаёт новую Recording, её первое размещение ReleaseTrack '
            'в указанном альбоме и связанный товар. Принимает '
            'оригинальный аудиофайл через multipart/form-data. '
            'Этот способ оставлен для простых одиночных '
            'загрузок и обратной совместимости. '
            'Для больших файлов и стабильной загрузки '
            'рекомендуется использовать '
            'прямую загрузку: инициализация → загрузка файла '
            'по transport-инструкции '
            '→ завершение загрузки.'
        ),
        request=TrackWriteSerializer,
        responses={201: TrackReadDetailSerializer},
    ),
    partial_update=extend_schema(
        summary='Частично обновить трек',
        tags=TRACKS_TAGS,
        description=(
            'Обновляет только переданные поля. Название, описание, ISRC '
            'и аудиофайл относятся к Recording и меняются во всех её '
            'размещениях; цена и разрешение переплаты относятся к товару '
            'конкретного ReleaseTrack. '
            'Если передан audio_file, файл загружается '
            'через backend простым '
            'multipart-способом. Для больших файлов предпочтительнее '
            'прямой upload flow.'
        ),
        request=TrackWriteSerializer,
        responses={200: TrackReadDetailSerializer},
    ),
    destroy=extend_schema(
        summary='Удалить трек',
        tags=TRACKS_TAGS,
        description=(
            'Деактивирует размещение ReleaseTrack. Связанная Recording '
            'и другие её размещения не удаляются. Трек с историей '
            'приобретения удалить нельзя.'
        ),
        responses={
            204: OpenApiResponse(description='ReleaseTrack деактивирован.'),
            409: OpenApiResponse(
                description='У трека или его релиза есть история продаж.',
            ),
        },
    ),
)


def album_track_create_schema(view_func):
    """Документирует размещение существующей записи в релизе."""
    return extend_schema(
        methods=['POST'],
        summary='Добавить существующую запись в релиз',
        description=(
            'Создаёт ReleaseTrack и связанный товар для существующей '
            'Recording в альбоме из URL. Оригинальный файл повторно '
            'загружать не нужно. recording_id — ID Recording; ID в ответе '
            '— ID нового ReleaseTrack. Пользователь должен иметь права '
            'и на релиз, и на владельца Recording. Одну Recording нельзя '
            'добавить в один релиз повторно.'
        ),
        request=TrackPlacementCreateSerializer,
        responses={
            201: TrackReadDetailSerializer,
            400: OpenApiResponse(
                description=(
                    'Запись недоступна, несовместима с артистом релиза '
                    'или уже размещена в этом релизе.'
                ),
            ),
            403: OpenApiResponse(
                description='Нет прав на релиз или мастер-запись.',
            ),
            404: OpenApiResponse(description='Альбом не найден.'),
        },
        tags=TRACKS_TAGS,
    )(view_func)


def track_reorder_schema(view_func):
    """Декоратор для документирования экшена изменения порядка треков."""
    return extend_schema(
        methods=['PATCH'],
        summary='Изменить порядок треков',
        description=(
            'Изменяет порядок всех активных треков указанного альбома. '
            'Необходимо передать ID альбома и полный список ID его '
            'треков в требуемом порядке.'
        ),
        request=TrackReorderSerializer,
        responses={
            200: TrackReadSerializer(many=True),
        },
        tags=TRACKS_TAGS,
        filters=False,
    )(view_func)
