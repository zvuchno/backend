"""Миксины вьюсетов."""

from django.db import transaction

from store.services import ProductService


class ProductActionMixin:
    """Миксин для ViewSet, обеспечивающий коммерческую обвязку контента.

    Использует ProductService для гарантии существования связанных
    объектов (Product/Variant) и выполняет синхронизацию их полей
    на основе данных из сериализатора.
    """

    def _update_product_data(self, instance, validated_data) -> None:
        """Вспомогательный метод для синхронизации цен."""
        price = validated_data.get('price')
        allow_overpay = validated_data.get('allow_overpay')

        product = ProductService.ensure_commerce(instance)

        update_fields = []
        if price is not None:
            product.price = price
            update_fields.append('price')
        if allow_overpay is not None:
            product.allow_overpay = allow_overpay
            update_fields.append('allow_overpay')

        if update_fields:
            product.save(update_fields=update_fields)

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(owner=self.request.user)
            self._update_product_data(instance, serializer.validated_data)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._update_product_data(instance, serializer.validated_data)
