"""Модуль сервисного слоя для управления корзинами покупок.

Содержит бизнес-логику для создания, обновления и синхронизации
содержимого корзины, инкапсулируя работу с БД и массовые операции.
"""

from decimal import Decimal

from django.db import transaction

from store.models import Cart, CartItem, ProductVariant


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
    def update_cart_items(
        cart: Cart,
        items_data: list,
        partial: bool = False,
    ) -> Cart:
        """Синхронизация товаров в корзине.

        Использует bulk_create и оптимизированные запросы для обновления
        количества товаров и удаления отсутствующих позиций.
        """
        current_items = {
            item.product_variant_id: item
            for item in CartItem.objects.filter(cart=cart)
        }

        incoming_variant_ids = [
            item['product_variant'].id for item in items_data
        ]

        # Если PUT — удаляем чего нет в запросе
        if not partial:
            cart.items.exclude(
                product_variant_id__in=incoming_variant_ids,
            ).delete()

        new_items = []
        updated_items = []

        for item_data in items_data:
            variant = item_data['product_variant']
            quantity = item_data['quantity']
            price_with_donation = item_data.get('price_with_donation')
            comment = item_data.get('comment')
            is_sub = item_data.get('is_artist_subscription', False)

            if variant.id in current_items:
                item = current_items[variant.id]
                if (
                    item.quantity != quantity
                    or item.price_with_donation != price_with_donation
                    or item.comment != comment
                    or item.is_artist_subscription != is_sub
                ):
                    item.quantity = quantity
                    item.price_with_donation = price_with_donation
                    item.comment = comment
                    item.is_artist_subscription = is_sub
                    updated_items.append(item)
            else:
                new_items.append(
                    CartItem(
                        cart=cart,
                        product_variant=variant,
                        quantity=quantity,
                        price_with_donation=price_with_donation,
                        comment=comment,
                        is_artist_subscription=is_sub,
                    ),
                )

        if updated_items:
            CartItem.objects.bulk_update(
                updated_items,
                [
                    'quantity',
                    'price_with_donation',
                    'comment',
                    'is_artist_subscription',
                ],
            )

        if new_items:
            CartItem.objects.bulk_create(new_items)

        return cart

    @staticmethod
    def remove_from_cart(cart: Cart, variant_id: int) -> bool:
        """Удаляет товар и возвращает True, если он был найден."""
        deleted_count, _ = cart.items.filter(
            product_variant_id=variant_id,
        ).delete()
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

        guest_cart = (
            Cart.objects
            .filter(
                session_key=session_key,
            )
            .prefetch_related('items__product_variant__product')
            .first()
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
                        guest_item.is_artist_subscription,
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
