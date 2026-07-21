"""ViewSet для работы с заказом покупателя."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch
from django.utils import timezone
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsUserObjectOwner
from common.utils import get_client_ip

from store.constants import RESERVATION_TTL_MINUTES
from store.exceptions import NotEnoughStock, PromocodeNotAvailable
from store.models import Image, Order, OrderItem
from store.schema import checkout_schema, order_schema
from store.serializers import (
    CheckoutInfoSerializer,
    CheckoutSerializer,
    OrderDetailSerializer,
    OrderSerializer,
)
from store.services import (
    CDEKService,
    CartService,
    LocationService,
    OrderService,
    ReservationService,
)


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
            return (permissions.IsAuthenticated(),)
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
            .order_by('-created_at')
        )

    @checkout_schema
    @action(detail=False, methods=['get', 'post'], url_path='checkout')
    def checkout(self, request):
        user = request.user if request.user.is_authenticated else None
        cart = CartService.get_or_create_cart(request)
        ip_address = get_client_ip(request)

        # GET
        if request.method == 'GET':
            city_fias_id = LocationService().get_fias_by_ip(ip_address)[
                'city_fias_id'
            ]
            city_data = CDEKService().get_city_info_by_fias(city_fias_id) or {}

            data = OrderService.checkout_info(
                user=user,
                cart=cart,
                city=city_data.get('city', ''),
                city_code=city_data.get('city_code', ''),
            )
            return Response(CheckoutInfoSerializer(data).data)

        # POST
        serializer = CheckoutSerializer(
            data=request.data,
            context={'request': request, 'cart': cart},
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                order = OrderService.create_order(
                    user=user,
                    cart=cart,
                    validated_data=serializer.validated_data,
                    ip_address=ip_address,
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                )
                order = ReservationService.reserve_order(
                    order,
                    reserved_until=(
                        timezone.now()
                        + timedelta(
                            minutes=RESERVATION_TTL_MINUTES,
                        )
                    ),
                )
        except NotEnoughStock as exc:
            raise ValidationError({'detail': str(exc)})

        except PromocodeNotAvailable as exc:
            raise ValidationError({'promocode': str(exc)})

        return Response(
            self.get_serializer(order).data,
            status=status.HTTP_201_CREATED,
        )
