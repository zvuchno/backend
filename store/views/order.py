"""ViewSet для работы с заказом покупателя."""

from django.db.models import Count, Prefetch
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsUserObjectOwner

from store.models import Image, Order, OrderItem
from store.schema import checkout_schema, order_schema
from store.serializers import (
    CheckoutSerializer,
    OrderDetailSerializer,
    OrderSerializer,
)
from store.services import CartService, OrderService


@order_schema
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """API заказа покупателя."""

    queryset = Order.objects.all()  # Для introspection drf-spectacular
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

    def get_permissions(self):
        if self.action == 'checkout':
            return (permissions.AllowAny(),)
        return super().get_permissions()

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

        items_qs = (
            OrderItem.objects
            .with_target_annotations()
            .select_related(
                'product_variant__product',
                'product_variant__product__album',
                'product_variant__product__track__album',
                'product_variant__product__merch',
            )
            .prefetch_related(
                Prefetch(
                    'product_variant__product__merch__images_merch',
                    queryset=Image.objects.order_by('-is_main', 'id'),
                ),
            )
        )
        return (
            Order.objects
            .filter(user=user)
            .annotate(items_count_annotated=Count('items'))
            .prefetch_related(
                Prefetch('items', queryset=items_qs),
            )
        )

    @checkout_schema
    @action(detail=False, methods=['get', 'post'], url_path='checkout')
    def checkout(self, request):
        user = request.user if request.user.is_authenticated else None
        cart = CartService.get_or_create_cart(request)

        # GET
        if request.method == 'GET':
            return Response(OrderService.checkout_info(user=user, cart=cart))

        # POST
        serializer = CheckoutSerializer(
            data=request.data,
            context={'request': request, 'cart': cart},
        )
        serializer.is_valid(raise_exception=True)

        order = OrderService.create_order(
            user=request.user,
            cart=cart,
            validated_data=serializer.validated_data,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
        )
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )
