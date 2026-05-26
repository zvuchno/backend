from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from store.filters import ProductCatalogFilter
from store.models import Product
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
        return (
            Product.objects
            .published_content()
            .with_card_data()
            .with_catalog_created_at()
        )
