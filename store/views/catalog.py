from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from store.models import Product
from store.serializers import CatalogCardSerializer


class ProductCatalogListView(ListAPIView):
    """Список товаров каталога."""

    serializer_class = CatalogCardSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        return Product.objects.published_content().with_card_data()
