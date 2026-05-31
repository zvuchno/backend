from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from store.filters import ProductCatalogFilter
from store.models import Favorite, Product
from store.schema import catalog_list_schema
from store.serializers import CatalogCardSerializer


@catalog_list_schema
class ProductCatalogListView(ListAPIView):
    """Список товаров каталога."""

    serializer_class = CatalogCardSerializer
    permission_classes = (AllowAny,)
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
    )
    filterset_class = ProductCatalogFilter
    search_fields = (
        'album__name',
        'merch__name',
        'album__owner__artist_profile__name',
        'merch__owner__artist_profile__name',
    )

    def get_queryset(self):
        """Возвращает товары каталога."""
        catalog_type = self.request.query_params.get('type')
        kind = self.request.query_params.get('kind')
        if kind:
            return Product.objects.for_merch_cards()
        return Product.objects.for_catalog_type(catalog_type)

    def get_serializer_context(self):
        """Возвращает контекст сериализатора."""
        context = super().get_serializer_context()
        user = self.request.user

        if user.is_authenticated:
            context['favorite_product_ids'] = set(
                Favorite.objects.filter(
                    user=user,
                ).values_list(
                    'product_variant__product_id',
                    flat=True,
                ),
            )
        else:
            context['favorite_product_ids'] = set()

        return context
