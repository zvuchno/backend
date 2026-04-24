from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import ArtistLegalSerializer

artist_legal_data_schema = extend_schema_view(
    get=extend_schema(
        tags=['Artists'],
        summary='Получить юридические данные артиста',
        description=(
            'Возвращает юридический профиль, паспортные и банковские '
            'данные текущего артиста.'
        ),
        responses=ArtistLegalSerializer,
    ),
    patch=extend_schema(
        tags=['Artists'],
        summary='Обновить юридические данные артиста',
        description=(
            'Частично обновляет юридический профиль, паспортные и банковские '
            'данные текущего артиста. Отсутствующие блоки не изменяются.'
        ),
        request=ArtistLegalSerializer,
        responses=ArtistLegalSerializer,
    ),
)
