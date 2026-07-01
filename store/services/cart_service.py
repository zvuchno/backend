"""Модуль сервисного слоя для управления корзинами покупок.

Содержит бизнес-логику для создания, обновления и синхронизации
содержимого корзины, инкапсулируя работу с БД и массовые операции.
"""

import logging
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from store.models import Cart, CartItem, ProductVariant
from store.services import CartCalculationService

logger = logging.getLogger('cart_debug')


class CartService:
    """Сервис для управления корзиной покупок."""

    @staticmethod
    @transaction.atomic
    def add_to_cart(
        cart: Cart,
        variant: ProductVariant,
        quantity: int,
        price_with_donation: Decimal = None,
        comment: str = '',
        is_artist_subscription: bool = False,
    ) -> CartItem:
        """Добавление товара в корзину.

        Если товар данного варианта уже есть в корзине,
        увеличивает его количество (инкрементальное обновление).
        """
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_variant=variant,
            defaults={
                'quantity': quantity,
                'price_with_donation': price_with_donation,
                'comment': comment,
                'is_artist_subscription': is_artist_subscription,
            },
        )
        if not created:
            item.quantity += quantity
            update_fields = ['quantity']

            if price_with_donation is not None:
                item.price_with_donation = price_with_donation
                update_fields.append('price_with_donation')

            if comment is not None:
                item.comment = comment
                update_fields.append('comment')

            if is_artist_subscription:
                item.is_artist_subscription = True
                update_fields.append('is_artist_subscription')

            item.save(update_fields=update_fields)

        return item

    @staticmethod
    @transaction.atomic
    def update_cart_items(cart: Cart, items_data: list) -> Cart:
        """Обновление количества товаров в корзине."""
        current_items = {
            item.product_variant_id: item
            for item in CartItem.objects.filter(cart=cart)
        }
        updated_items = []
        for item_data in items_data:
            variant = item_data['product_variant']
            quantity = item_data['quantity']
            if variant.id not in current_items:
                raise ValidationError(
                    {
                        'product_variant': f'Товар с ID={variant.id} '
                        'не найден в корзине',
                    },
                )
            item = current_items[variant.id]
            if item.quantity != quantity:
                item.quantity = quantity
                updated_items.append(item)
        if updated_items:
            CartItem.objects.bulk_update(updated_items, ['quantity'])
        return cart

    @staticmethod
    def remove_from_cart(cart: Cart, variant_id: int) -> bool:
        """Удаляет товар и возвращает True, если он был найден."""
        deleted_count, _ = cart.items.filter(
            product_variant_id=variant_id,
        ).delete()

        if deleted_count > 0 and cart.promocode:
            cart.refresh_from_db()
            CartService.validate_cart_promocode(cart)

        return deleted_count > 0

    @staticmethod
    def get_or_create_cart(request) -> Cart:
        """Получить или создать корзину."""
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        # для гостя
        if not request.session.session_key:
            request.session.create()

        cart, _ = Cart.objects.get_or_create(
            session_key=request.session.session_key,
        )
        return cart

    @staticmethod
    @transaction.atomic
    def merge_carts(user, request) -> None:
        """Объединить гостевую корзину с пользовательской."""
        session_key = request.session.session_key
        if not session_key:
            return

        logger.warning('=== MERGE CARTS DEBUG ===')
        logger.warning(
            f'merge_carts called for user={user}, session_key={session_key}',
        )

        guest_cart = (
            Cart.objects
            .filter(
                session_key=session_key,
            )
            .prefetch_related('items__product_variant__product')
            .first()
        )
        logger.warning(f'guest_cart found: {guest_cart}')
        logger.warning(
            f'No cart found with session_key={session_key} — '
            'checking all carts with session_key set',
        )
        logger.warning(
            f'All session-based carts: {
                list(
                    Cart.objects.exclude(session_key__isnull=True).values(
                        "id", "session_key"
                    )
                )
            }',
        )

        if not guest_cart:
            return

        user_cart, _ = Cart.objects.get_or_create(user=user)

        for guest_item in guest_cart.items.all():
            variant = guest_item.product_variant
            product = variant.product

            user_item, created = CartItem.objects.get_or_create(
                cart=user_cart,
                product_variant=variant,
                defaults={
                    'quantity': guest_item.quantity,
                    'price_with_donation': guest_item.price_with_donation,
                    'comment': guest_item.comment,
                    'is_artist_subscription': (
                        guest_item.is_artist_subscription
                    ),
                },
            )
            if not created:
                # Считаем потенциальное новое количество
                total_qty = user_item.quantity + guest_item.quantity
                if product.product_type == 'merch':
                    # Ограничиваем остатком на складе, если он указан
                    if variant.stock is not None:
                        total_qty = min(total_qty, variant.stock)
                else:
                    # Для цифровых товаров всегда только 1
                    total_qty = 1

                if user_item.quantity != total_qty:
                    user_item.quantity = total_qty
                    user_item.save(update_fields=['quantity'])

                if (
                    guest_item.is_artist_subscription
                    and not user_item.is_artist_subscription
                ):
                    user_item.is_artist_subscription = True
                    user_item.save(update_fields=['is_artist_subscription'])
        # Удаляем гостевую корзину после переноса
        guest_cart.delete()
        user_cart.refresh_from_db()
        CartService.validate_cart_promocode(user_cart)

    @staticmethod
    def validate_cart_promocode(cart: Cart) -> None:
        """Проверяет актуальность промокода.

        Если промокод невалиден или нет подходящих товаров — дропает его.
        """
        if not cart.promocode:
            return

        if not cart.promocode.is_available:
            cart.promocode = None
            cart.save(update_fields=['promocode'])
            return

        # Проверяем наличие товаров владельца промокода
        calculation_service = CartCalculationService(cart)
        has_applicable_items = any(
            calculation_service._get_item_owner_id(item)
            == cart.promocode.owner_id
            for item in calculation_service.items
        )
        # Если подходящих товаров нет — дропаем промокод
        if not has_applicable_items:
            cart.promocode = None
            cart.save(update_fields=['promocode'])
