from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from store.serializers import (
    DownloadLinkSerializer,
    LibraryAlbumCardSerializer,
    PurchasedMusicDLDetailSerializer,
)

PURCHASED_MUSIC_TAGS = ['Listener']

purchased_music_schema = extend_schema_view(
    get=extend_schema(
        summary='Доступная музыка текущего слушателя',
        description=(
            'Возвращает список релизов, в которых текущему слушателю '
            'доступен хотя бы один трек. '
            'Флаг is_fully_available показывает, доступен ли релиз полностью.'
        ),
        tags=PURCHASED_MUSIC_TAGS,
        responses={200: LibraryAlbumCardSerializer(many=True)},
    ),
)

purchased_music_download_detail_schema = extend_schema(
    summary='Варианты скачивания доступного релиза',
    description=(
        'Возвращает доступные варианты скачивания одного релиза. '
        'Для полного доступа может вернуть ZIP-архив со статусом подготовки. '
        'Поле download_action_url зарезервировано для будущей ручки '
        'получения ссылки на скачивание и пока возвращается как null.'
    ),
    tags=PURCHASED_MUSIC_TAGS,
    responses={
        200: PurchasedMusicDLDetailSerializer,
    },
)

track_download_link_schema = extend_schema(
    summary='Получить ссылку на скачивание трека',
    description=(
        'Проверяет доступ текущего слушателя к треку и возвращает '
        'короткоживущую ссылку на скачивание.'
    ),
    tags=PURCHASED_MUSIC_TAGS,
    responses={
        200: DownloadLinkSerializer,
        404: OpenApiResponse(
            description='Трек недоступен или файл отсутствует.',
        ),
    },
)

archive_download_link_schema = extend_schema(
    summary='Получить ссылку на ZIP-архив релиза',
    description=(
        'Проверяет полный доступ текущего слушателя к релизу и '
        'возвращает короткоживущую ссылку на готовый ZIP-архив.'
    ),
    tags=PURCHASED_MUSIC_TAGS,
    responses={
        200: DownloadLinkSerializer,
        404: OpenApiResponse(
            description='Релиз недоступен или файл отсутствует.',
        ),
        409: OpenApiResponse(
            description='Архив ещё не готов.',
        ),
    },
)
