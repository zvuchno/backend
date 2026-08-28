from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from store.serializers import CatalogSearchSerializer
from store.services.catalog_search import CatalogSearchService


class CatalogSearchView(ListAPIView):
    """Глобальный поиск по каталогу."""

    serializer_class = CatalogSearchSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, UserRateThrottle)

    def get_queryset(self):
        """Возвращает результаты глобального поиска."""
        query = self.request.query_params.get('q', '')

        return CatalogSearchService.search(query)
