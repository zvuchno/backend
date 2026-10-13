from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

from store.serializers import (
    MerchDetailSerializer,
    MerchReadSerializer,
    MerchReorderSerializer,
    MerchWriteSerializer,
)

# Описание логики работы с вариантами для API документации
VARIANTS_DESCRIPTION = (
    'Если поле `variants` передано — оно должно содержать '
    'ПОЛНЫЙ список вариантов. Отсутствующие варианты будут деактивированы.\n\n'
    'Логика работы с вариантами:\n'
    '- вариант без `id` → создаёт\n'
    '- вариант с `id` → обновляет\n'
    '- вариант отсутствует в списке → деактивирует\n'
    '- нет `id`, но значение есть среди деактивированных '
    '→ реанимирует и обновляет\n'
    '- `variants: []` → деактивирует все'
)

MERCH_TAGS = ['Merch']

merch_schema = extend_schema_view(
    list=extend_schema(
        summary='Список мерча',
        tags=MERCH_TAGS,
        description='Возвращает список мерча.',
        parameters=[
            OpenApiParameter(
                name='kind',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Фильтр по slug типа мерча',
            ),
            OpenApiParameter(
                name='in_stock',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Фильтр по наличию',
            ),
            OpenApiParameter(
                name='kind',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Фильтр по slug типа мерча',
            ),
            OpenApiParameter(
                name='album',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Фильтр по ID альбома',
            ),
            OpenApiParameter(
                name='artist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Фильтр по ID артиста',
            ),
            OpenApiParameter(
                name='artist_name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Поиск по имени артиста',
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Общий поиск (название, описание)',
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Сортировка (name, created_at)',
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
    ),
    retrieve=extend_schema(
        summary='Получить мерч',
        tags=MERCH_TAGS,
        description='Возвращает мерч по id.',
    ),
    create=extend_schema(
        summary='Создать мерч',
        tags=MERCH_TAGS,
        request=MerchWriteSerializer,
        responses={201: MerchDetailSerializer},
        description=(f'Создаёт новый мерч.\n\n{VARIANTS_DESCRIPTION}'),
    ),
    partial_update=extend_schema(
        summary='Частично обновить мерч',
        tags=MERCH_TAGS,
        request=MerchWriteSerializer,
        responses={200: MerchDetailSerializer},
        description=(
            'Обновляет поля мерча. '
            'Изображения обновляются через отдельные эндпоинты.'
            f'\n\n{VARIANTS_DESCRIPTION}'
        ),
    ),
    destroy=extend_schema(
        summary='Удалить мерч',
        tags=MERCH_TAGS,
        description='Удаляет мерч.',
    ),
)


def merch_reorder_schema(view_func):
    """Декоратор для документирования экшена изменения порядка мерча."""
    return extend_schema(
        methods=['PATCH'],
        summary='Изменить порядок мерча',
        description=(
            'Изменяет порядок всего активного мерча указанного артиста, '
            'доступного пользователю. Необходимо передать ID артиста и '
            'полный список ID его мерча в требуемом порядке.'
        ),
        request=MerchReorderSerializer,
        responses={
            200: MerchReadSerializer(many=True),
        },
        tags=MERCH_TAGS,
        filters=False,
    )(view_func)
