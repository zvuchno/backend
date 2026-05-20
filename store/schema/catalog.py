from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

catalog_schema = extend_schema(
    summary='Каталог',
    tags=['Catalog'],
    description=(
        'Возвращает карточки каталога.\n\n'
        'Без параметра type возвращает блоки для главной страницы: '
        'albums, carriers, merch по несколько карточек каждого типа.\n\n'
        'С параметром type возвращает плоский список карточек для ленты '
        'или кнопки "Загрузить ещё".'
    ),
    parameters=[
        OpenApiParameter(
            name='type',
            type=OpenApiTypes.STR,
            enum=['all', 'album', 'carrier', 'merch'],
            location=OpenApiParameter.QUERY,
            required=False,
            description=(
                'Режим выдачи каталога. '
                'Если параметр не передан - возвращаются отдельные блоки '
                'для главной страницы. '
                'all - смешанная лента: альбомы, носители и мерч. '
                'album - только альбомы. '
                'carrier - только физические носители альбомов. '
                'merch - только обычный мерч.'
            ),
        ),
        OpenApiParameter(
            name='offset',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description=(
                'Смещение для режима плоской ленты. '
                'Используется с type=all, type=album, type=carrier '
                'или type=merch. '
                'Для кнопки "Загрузить ещё" фронт должен использовать URL '
                'из поля next, а не рассчитывать offset самостоятельно.'
            ),
        ),
        OpenApiParameter(
            name='ordering',
            type=OpenApiTypes.STR,
            enum=['-created_at', 'created_at', 'random'],
            location=OpenApiParameter.QUERY,
            required=False,
            description=(
                'Сортировка карточек в режиме плоской ленты. '
                '-created_at - сначала новые, используется по умолчанию. '
                'created_at - сначала старые. '
                'random - случайный порядок в текущей пачке.'
            ),
        ),
    ],
)
