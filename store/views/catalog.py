from django_filters.rest_framework import DjangoFilterBackend
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
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProductCatalogFilter

    def get_queryset(self):
        return (
            Product.objects
            .published_content()
            .with_card_data()
            .with_catalog_created_at()
        )
