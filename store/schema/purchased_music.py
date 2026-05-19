"""Схемы автодокументации OpenAPI для купленной музыки."""

from drf_spectacular.utils import extend_schema, extend_schema_view

from store.serializers import PurchasedMusicSerializer

PURCHASED_MUSIC_TAGS = ['Customer: Purchased music']

purchased_music_schema = extend_schema_view(
    get=extend_schema(
        summary='Купленная музыка текущего слушателя',
        description=(
            'Возвращает библиотеку купленной музыки текущего слушателя: '
            'полностью доступные альбомы и отдельно купленные треки.'
        ),
        tags=PURCHASED_MUSIC_TAGS,
        responses={200: PurchasedMusicSerializer},
    ),
)
