from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from store.filters import ProductCatalogFilter
from store.models import Product
from store.schema import catalog_schema
from store.serializers import ProductCatalogListSerializer


@catalog_schema
class ProductCatalogListView(ListAPIView):
    """Список товаров каталога."""

    serializer_class = ProductCatalogListSerializer
    permission_classes = (AllowAny,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProductCatalogFilter

    def get_queryset(self):
        queryset = Product.objects.visible_for_catalog().with_content()
        if self.request.user.is_authenticated:
            queryset = queryset.with_is_favorite(user=self.request.user)

        return queryset
