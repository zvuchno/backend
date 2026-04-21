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
        # Сначала гарантируем базовые связи
        product = ProductService.ensure_commerce(instance)

        update_fields = []
        # Обновляем общие поля продукта
        price = validated_data.get('price')
        allow_overpay = validated_data.get('allow_overpay')
        if price is not None:
            product.price = price
            update_fields.append('price')
        if allow_overpay is not None:
            product.allow_overpay = allow_overpay
            update_fields.append('allow_overpay')

        if update_fields:
            product.save(update_fields=update_fields)

        # Специфичная логика для мерча
        if instance._meta.model_name == 'merch':
            ProductService.sync_merch_variants(
                product=product,
                stock=validated_data.get('stock', 0),
                variants_data=validated_data.get('variants'),
            )

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(owner=self.request.user)
            self._update_product_data(instance, serializer.validated_data)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._update_product_data(instance, serializer.validated_data)