"""ViewSet для работы с заказом покупателя."""

from rest_framework import filters, mixins, viewsets

from common.permissions import IsUserObjectOwner

from store.models import Order
from store.schema import order_schema
from store.serializers import OrderDetailSerializer, OrderSerializer


@order_schema
class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """API заказа покупателя."""

    queryset = Order.objects.all()
    serializer_class = OrderSerializer
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
        """Возвращает заказы текущего пользователя."""
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()

        return (
            Order.objects
            .filter(
                user=user,
            )
            .prefetch_related(
                'items',
            )
            .distinct()
        )
