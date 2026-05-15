"""ViewSet для работы с историей продаж продавца."""

from django.db.models import Count, Prefetch, Q
from rest_framework import filters, viewsets

from common.permissions import IsArtist, IsSalesOwner

from store.models import Image, Order, OrderItem
from store.schema import artist_sale_schema
from store.serializers import (
    ArtistSaleDetailSerializer,
    ArtistSaleSerializer,
)


@artist_sale_schema
class ArtistSaleViewSet(viewsets.ReadOnlyModelViewSet):
    """API продаж артиста."""

    queryset = Order.objects.all()
    permission_classes = (IsArtist, IsSalesOwner)
    filter_backends = (filters.SearchFilter,)
    search_fields = (
        'order_number',
        'items__product_info__name',
        'items__product_info__sku',
    )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ArtistSaleDetailSerializer
        return ArtistSaleSerializer

    def get_queryset(self):
        """Возвращает заказы, текущего артиста.

        Особенности:
        - артист видит только те заказы, где присутствуют его товары
        - `items` в заказе - только позиции этого артиста
        """
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()

        # Заказы, где есть товары этого артиста
        order_filter = (
            Q(items__product_variant__product__album__owner=user)
            | Q(items__product_variant__product__track__owner=user)
            | Q(items__product_variant__product__merch__owner=user)
        )
        # Фильтр items - только позиции этого артиста
        items_filter = (
            Q(product_variant__product__album__owner=user)
            | Q(product_variant__product__track__owner=user)
            | Q(product_variant__product__merch__owner=user)
        )

        # Queryset для items
        items_qs = (
            OrderItem.objects
            .filter(items_filter)
            .select_related(
                'product_variant__product',
                'product_variant__product__album',
                'product_variant__product__track__album',
                'product_variant__product__merch',
            )
            # Изображения мерча, отсортированные -is_main
            .prefetch_related(
                Prefetch(
                    'product_variant__product__merch__images_merch',
                    queryset=Image.objects.order_by('-is_main', 'id'),
                ),
            )
        )

        return (
            Order.objects
            # Только заказы, где есть товары артиста
            .filter(order_filter)
            .annotate(
                # Количество позиций артиста в заказе
                items_count_annotated=Count(
                    'items',
                    filter=order_filter,
                ),
            )
            .prefetch_related(
                Prefetch('items', queryset=items_qs),
            )
            .distinct()
        )
