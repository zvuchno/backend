"""ViewSet для работы с корзиной покупателя."""

from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from store.constants import ZERO_MONEY
from store.models import Cart, CartItem
from store.schema import (
    cart_apply_promocode_schema,
    cart_remove_promocode_schema,
    cart_schema,
)
from store.serializers import (
    ApplyPromocodeSerializer,
    CartItemWriteSerializer,
    CartReadSerializer,
    CartWriteSerializer,
)
from store.services import CartCalculationService, CartService

# Возвращается на GET /cart/me/ если корзина ещё не создана
EMPTY_CART_RESPONSE = {
    'items': [],
    'subtotal': ZERO_MONEY,
    'discount_promocode': ZERO_MONEY,
    'total': ZERO_MONEY,
}


@cart_schema
class CartViewSet(viewsets.GenericViewSet):
    """API для управления корзиной покупок пользователя.

    Управление корзиной:
    - GET: Получить состав корзины.
    - PUT: Полная синхронизация.
    - PATCH: Частичное обновление.
    - POST: Добавить один товар или увеличить количество.
    - DELETE: Удалить товар полностью.
    """

    queryset = Cart.objects.all()
    http_method_names = ('get', 'post', 'put', 'patch', 'delete')
    permission_classes = (AllowAny,)

    def get_queryset(self):
        """Фильтрация корзины для текущего пользователя или анонима."""
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            queryset = queryset.filter(user=user)
        else:
            # Если юзер аноним, ищем по сессии
            session_key = self.request.session.session_key
            if not session_key:
                return queryset.none()
            queryset = queryset.filter(session_key=session_key)

        # Применяем метод кверисета CartQuerySet
        return queryset.with_subtotal().prefetch_related(
            Prefetch(
                'items',
                # Оптимизируем вложенные айтемы через CartItemQuerySet
                queryset=CartItem.objects
                .with_prices()
                .with_target_annotations()
                .select_related(
                    'product_variant__product__track',
                    'product_variant__product__album',
                    'product_variant__product__merch',
                ),
            ),
        )

    def get_instance(self):
        """Возвращает или создает корзину, кэшируя её в рамках запроса."""
        if not hasattr(self, '_cached_cart'):
            self._cached_cart = CartService.get_or_create_cart(self.request)
        return self._cached_cart

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CartReadSerializer
        return CartWriteSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        cart = getattr(self, 'instance', None) or getattr(
            self,
            '_cached_cart',
            None,
        )
        context['cart'] = cart

        if cart:
            service = CartCalculationService(cart)
            context.update(service.get_serializer_context())

        return context

    @action(detail=False, methods=('get', 'put', 'patch'), url_path='me')
    def me(self, request):
        """Получение или обновление корзины текущего пользователя."""
        if request.method == 'GET':
            cart = self.get_queryset().first()
            if cart is None:
                return Response(EMPTY_CART_RESPONSE)
        else:  # PUT/PATCH
            cart = self.get_instance()
            serializer = self.get_serializer(
                cart,
                data=request.data,
                partial=(request.method == 'PATCH'),
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            cart = self.get_queryset().get(pk=cart.pk)
        self._cached_cart = cart
        self.instance = cart
        return Response(
            CartReadSerializer(
                cart,
                context=self.get_serializer_context(),
            ).data,
        )

    @action(detail=False, methods=['post'], url_path='me/add')
    def add_item(self, request):
        """Добавить товар (умное добавление)."""
        cart = self.get_instance()
        variant_id = request.data.get('product_variant')
        instance = cart.items.filter(product_variant_id=variant_id).first()
        serializer = CartItemWriteSerializer(
            instance=instance,
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        CartService.add_to_cart(
            cart=cart,
            variant=serializer.validated_data['product_variant'],
            quantity=serializer.validated_data['quantity'],
            price_with_donation=serializer.validated_data.get(
                'price_with_donation',
            ),
            comment=serializer.validated_data.get('comment'),
            is_artist_subscription=(
                serializer.validated_data.get('is_artist_subscription')
            ),
        )

        cart = self.get_queryset().get(pk=cart.pk)
        self._cached_cart = cart
        self.instance = cart

        return Response(
            CartReadSerializer(
                cart,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=['delete'],
        url_path=r'me/remove/(?P<variant_id>\d+)',
    )
    def remove_item(self, request, variant_id=None):
        """Удалить товар из корзины."""
        cart = self.get_instance()
        success = CartService.remove_from_cart(cart, variant_id)

        if not success:
            return Response(
                {'detail': 'Товар не найден в корзине'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Сбрасываем кэш, так как состав корзины изменился
        if hasattr(self, '_cached_cart'):
            delattr(self, '_cached_cart')

        return Response(status=status.HTTP_204_NO_CONTENT)

    @cart_apply_promocode_schema
    @action(detail=False, methods=['post'], url_path='apply-promocode')
    def apply_promocode(self, request):
        """Применить промокод."""
        cart = self.get_instance()

        context = self.get_serializer_context()
        context['cart'] = cart
        serializer = ApplyPromocodeSerializer(
            data=request.data,
            context=context,
        )
        serializer.is_valid(raise_exception=True)

        promocode = serializer.context['promocode']

        cart.promocode = promocode
        cart.save(update_fields=['promocode'])

        cart = self.get_queryset().get(pk=cart.pk)
        self._cached_cart = cart
        self.instance = cart

        return Response(
            CartReadSerializer(
                cart,
                context=self.get_serializer_context(),
            ).data,
        )

    @cart_remove_promocode_schema
    @action(detail=False, methods=['post'], url_path='remove-promocode')
    def remove_promocode(self, request):
        """Удалить промокод."""
        cart = self.get_instance()

        if cart.promocode:
            cart.promocode = None
            cart.save()

        cart = self.get_queryset().get(pk=cart.pk)
        self._cached_cart = cart
        self.instance = cart

        return Response(
            CartReadSerializer(
                cart,
                context=self.get_serializer_context(),
            ).data,
        )
