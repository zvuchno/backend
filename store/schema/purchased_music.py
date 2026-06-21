from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from store.serializers import (
    ArchiveNotReadySerializer,
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
        'Поле download_action_url содержит URL POST-ручки для получения '
        'свежей временной ссылки на скачивание. '
        'Для неподготовленного архива возвращается null.'
    ),
    tags=PURCHASED_MUSIC_TAGS,
    responses={
        200: PurchasedMusicDLDetailSerializer,
    },
)

track_download_link_schema = extend_schema(
    summary='Получить временную ссылку на скачивание трека',
    description=(
        'Проверяет доступ текущего слушателя к треку и возвращает '
        'короткоживущую ссылку на приватный файл. '
        'Ссылку следует использовать сразу после получения.'
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
    summary='Получить временную ссылку на ZIP-архив релиза',
    description=(
        'Проверяет полный доступ текущего слушателя к релизу и возвращает '
        'короткоживущую ссылку на готовый ZIP-архив. '
        'Если архив ещё собирается, возвращает его текущее состояние.'
    ),
    tags=PURCHASED_MUSIC_TAGS,
    responses={
        200: DownloadLinkSerializer,
        404: OpenApiResponse(
            description='Релиз недоступен или файл отсутствует.',
        ),
        409: ArchiveNotReadySerializer,
    },
)
