"""ViewSet для работы с заказом покупателя."""

from django.db.models import Count, Prefetch
from rest_framework import filters, viewsets

from common.permissions import IsUserObjectOwner

from store.models import Image, Order, OrderItem
from store.schema import order_schema
from store.serializers import OrderDetailSerializer, OrderSerializer


@order_schema
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """API заказа покупателя."""

    queryset = Order.objects.all()
    permission_classes = (IsUserObjectOwner,)
    filter_backends = (filters.SearchFilter,)
    search_fields = (
        'order_number',
        'items__product_info__name',
        'items__product_info__sku',
    )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderSerializer

    def get_queryset(self):
        """Возвращает заказы текущего пользователя.

        Запрос:
        - фильтрует заказы по текущему авторизованному пользователю
        - добавляет количество позиций в заказе (items_count_annotated)

        Оптимизация:
        - select_related - для связанных product объектов (album, track, merch)
        - prefetch_related - для items и изображений мерча
        - изображения мерча сортируются по приоритету главной (-is_main)
        """
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()

        items_qs = OrderItem.objects.select_related(
            'product_variant__product',
            'product_variant__product__album',
            'product_variant__product__track__album',
            'product_variant__product__merch',
        ).prefetch_related(
            Prefetch(
                'product_variant__product__merch__images_merch',
                queryset=Image.objects.order_by('-is_main', 'id'),
            ),
        )
        return (
            Order.objects
            .filter(user=user)
            .annotate(items_count_annotated=Count('items'))
            .prefetch_related(
                Prefetch('items', queryset=items_qs),
            )
        )
