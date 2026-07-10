"""Сервис резервирования и освобождения складских остатков."""

import logging

from django.db import transaction

from store.exceptions import NotEnoughStock
from store.models import Order, Product, ProductVariant

logger = logging.getLogger(__name__)


class ReservationService:
    """Сервис резервирования товаров."""

    @staticmethod
    @transaction.atomic
    def reserve_order(
        order,
        status=Order.Status.RESERVED,
        reserved_until=None,
    ) -> Order:
        """Резервирует мерч в заказе."""
        # Блокируем заказ
        order = Order.objects.select_for_update().get(pk=order.pk)

        order_items = list(
            order.items.filter(
                product_variant__product__product_type=Product.ProductType.MERCH,
            ).select_related('product_variant'),
        )

        variant_ids = [item.product_variant_id for item in order_items]

        # Блокируем остатки
        variants = (
            ProductVariant.objects
            .select_for_update()
            .select_related(
                'product',
            )
            .in_bulk(variant_ids)
        )

        # Проверка наличия
        for item in order_items:
            variant = variants[item.product_variant_id]

            if variant.stock < item.quantity:
                raise NotEnoughStock(
                    f'Недостаточно товара "{variant.product.name}'
                    f'({variant.property_value})" на складе.',
                )

        # Списание
        variants_to_update = []
        for item in order_items:
            variant = variants[item.product_variant_id]
            variant.stock -= item.quantity
            variants_to_update.append(variant)
        ProductVariant.objects.bulk_update(variants_to_update, ['stock'])

        order.status = status
        order.reserved_until = reserved_until
        order.save(update_fields=['status', 'reserved_until', 'updated_at'])

        logger.info(
            'Заказ id=%s зарезервирован до %s.',
            order.id,
            order.reserved_until,
        )
        return order

    @staticmethod
    @transaction.atomic
    def release_order_reserve(order, status=Order.Status.CREATED) -> Order:
        """Снимает резерв с мерча в заказе."""
        # Блокируем заказ
        order = Order.objects.select_for_update().get(pk=order.pk)

        order_items = list(
            order.items.filter(
                product_variant__product__product_type=Product.ProductType.MERCH,
            ).select_related('product_variant'),
        )

        variant_ids = [item.product_variant_id for item in order_items]

        # Блокируем остатки
        variants = (
            ProductVariant.objects
            .select_for_update()
            .select_related(
                'product',
            )
            .in_bulk(variant_ids)
        )

        variants_to_update = []
        for item in order_items:
            variant = variants[item.product_variant_id]
            variant.stock += item.quantity
            variants_to_update.append(variant)

        if variants_to_update:
            ProductVariant.objects.bulk_update(
                variants_to_update,
                ['stock'],
            )

        order.status = status
        order.reserved_until = None
        order.save(
            update_fields=[
                'status',
                'reserved_until',
                'updated_at',
            ],
        )

        logger.info(
            'Резерв заказа id=%s снят.',
            order.id,
        )
        return order
