"""Миксины вьюсетов."""

from django.db import transaction

from store.services import ProductService


class ProductActionMixin:
    """Миксин для ViewSet, интегрирующий контент с коммерческим слоем системы.

    Обеспечивает автоматический запуск бизнес-логики через ProductService
    после успешного сохранения основной модели. Гарантирует наличие
    связанных объектов (Product/Variant) и актуализацию их данных
    на основе входящего запроса.
    """

    def _update_product_data(self, instance, validated_data) -> None:
        """Инициирует процесс синхронизации коммерческих данных.."""
        ProductService.ensure_commerce(instance, validated_data)

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(owner=self.request.user)
            self._update_product_data(instance, serializer.validated_data)
            instance.refresh_from_db()

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._update_product_data(instance, serializer.validated_data)
            instance.refresh_from_db()
