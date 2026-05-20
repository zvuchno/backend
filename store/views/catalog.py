import random
from itertools import chain

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from config import settings
from store.models import Album, Merch
from store.schema import catalog_schema
from store.serializers import (
    CatalogAlbumSerializer,
    CatalogCarrierSerializer,
    CatalogMerchSerializer,
)


@catalog_schema
class CatalogView(APIView):
    """Представление каталога."""

    default_limit: int = sum(settings.CATALOG_MIX.values())
    allowed_ordering = ('created_at', '-created_at', 'random')
    allowed_types = ('all', 'album', 'carrier', 'merch', None)

    def get(self, request):
        """Возвращает карточки каталога."""
        catalog_type = request.query_params.get('type')

        if catalog_type is None:
            return self._get_homepage_response()

        if catalog_type not in self.allowed_types:
            return Response(
                {'type': 'Недопустимый тип каталога.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        offset = self._get_offset()
        batch_number = offset // self.default_limit

        items = self._get_items_by_type(catalog_type, batch_number)
        items = self._sort_items(items)

        return Response({
            'next': self._get_next_url(offset, len(items)),
            'results': items,
        })

    def _get_items_by_type(
        self,
        catalog_type: str,
        batch_number: int,
    ) -> list[dict]:
        """Возвращает карточки каталога по типу."""
        if catalog_type == 'all':
            return self._get_catalog_items(batch_number)

        limit = self.default_limit

        if catalog_type == 'album':
            return self._get_album_items(limit, batch_number)

        if catalog_type == 'carrier':
            return self._get_carrier_items(limit, batch_number)

        return self._get_merch_items(limit, batch_number)

    def _get_catalog_items(self, batch_number: int) -> list[dict]:
        """Возвращает общий список карточек каталога."""
        albums = self._get_album_items(
            limit=settings.CATALOG_MIX['album'],
            batch_number=batch_number,
        )
        carriers = self._get_carrier_items(
            limit=settings.CATALOG_MIX['carrier'],
            batch_number=batch_number,
        )
        merch = self._get_merch_items(
            limit=settings.CATALOG_MIX['merch'],
            batch_number=batch_number,
        )

        return list(chain(albums, carriers, merch))

    def _get_album_items(
        self,
        limit: int,
        batch_number: int,
    ) -> list[dict]:
        """Возвращает карточки альбомов."""
        start, stop = self._get_bounds(limit, batch_number)

        albums = (
            Album.objects
            .visible_for(self.request.user, 'list')
            .select_related('owner', 'owner__artist_profile', 'product')
            .order_by('-created_at')[start:stop]
        )

        return CatalogAlbumSerializer(
            albums,
            many=True,
            context=self.get_serializer_context(),
        ).data

    def _get_carrier_items(
        self,
        limit: int,
        batch_number: int,
    ) -> list[dict]:
        """Возвращает карточки носителей."""
        start, stop = self._get_bounds(limit, batch_number)

        carriers = (
            Merch.objects
            # .visible_for(self.request.user, 'list')
            .filter(is_carrier=True, album__isnull=False)
            .select_related(
                'owner',
                'owner__artist_profile',
                'album',
                'product',
            )
            .prefetch_related('images_merch')
            .order_by('-created_at')[start:stop]
        )

        return CatalogCarrierSerializer(
            carriers,
            many=True,
            context=self.get_serializer_context(),
        ).data

    def _get_merch_items(
        self,
        limit: int,
        batch_number: int,
    ) -> list[dict]:
        """Возвращает карточки обычного мерча."""
        start, stop = self._get_bounds(limit, batch_number)

        merch = (
            Merch.objects
            # .visible_for(self.request.user, 'list')
            .filter(is_carrier=False)
            .select_related('owner', 'owner__artist_profile', 'product')
            .prefetch_related('images_merch')
            .order_by('-created_at')[start:stop]
        )

        return CatalogMerchSerializer(
            merch,
            many=True,
            context=self.get_serializer_context(),
        ).data

    def _get_bounds(
        self,
        limit: int,
        batch_number: int,
    ) -> tuple[int, int]:
        """Возвращает границы среза для типа карточек."""
        start = batch_number * limit
        stop = start + limit
        return start, stop

    def _get_offset(self) -> int:
        """Возвращает offset из query params."""
        raw_offset = self.request.query_params.get('offset', 0)

        try:
            offset = int(raw_offset)
        except (TypeError, ValueError):
            return 0

        if offset < 0:
            return 0

        return offset // self.default_limit * self.default_limit

    def _get_next_url(self, offset: int, page_size: int) -> str | None:
        """Возвращает URL следующей порции каталога."""
        if page_size == 0:
            return None

        params = self.request.query_params.copy()
        params['offset'] = offset + self.default_limit

        return f'{self.request.path}?{params.urlencode()}'

    def get_serializer_context(self) -> dict:
        """Возвращает контекст сериализатора."""
        return {'request': self.request}

    def _sort_items(self, items: list[dict]) -> list[dict]:
        """Сортирует карточки каталога."""
        ordering = self.request.query_params.get('ordering', '-created_at')

        if ordering not in self.allowed_ordering:
            ordering = '-created_at'

        if ordering == 'random':
            random.shuffle(items)
            return items

        return sorted(
            items,
            key=lambda item: item['created_at'],
            reverse=ordering == '-created_at',
        )

    def _get_homepage_response(self) -> Response:
        """Возвращает блоки главной страницы каталога."""
        batch_number = 0
        preview_limit = settings.CARDS_PER_ROW

        return Response({
            'albums': self._get_album_items(
                preview_limit,
                batch_number,
            ),
            'carriers': self._get_carrier_items(
                preview_limit,
                batch_number,
            ),
            'merch': self._get_merch_items(
                preview_limit,
                batch_number,
            ),
        })
