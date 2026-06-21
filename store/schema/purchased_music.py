from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import (
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
        'Возвращает варианты скачивания одного релиза, доступного '
        'текущему слушателю. Для полного доступа может вернуть '
        'ZIP-архив со статусом подготовки. '
        'Прямые ссылки на файлы здесь еще не возвращаются.'
    ),
    tags=PURCHASED_MUSIC_TAGS,
    responses={
        200: PurchasedMusicDLDetailSerializer,
    },
)
