"""Миксины вьюсетов."""

from django.core.exceptions import FieldDoesNotExist
from django.db import transaction

from store.services import ProductService
from store.views.mixins.managed_artist import ManagedArtistActionMixin


class ProductActionMixin(ManagedArtistActionMixin):
    """Миксин для ViewSet, интегрирующий контент с коммерческим слоем системы.

    Обеспечивает автоматический запуск бизнес-логики через ProductService
    после успешного сохранения основной модели. Гарантирует наличие
    связанных объектов (Product/Variant) и актуализацию их данных
    на основе входящего запроса.
    """

    def _update_product_data(self, instance, validated_data) -> None:
        """Инициирует процесс синхронизации коммерческих данных..."""
        ProductService.ensure_commerce(instance, validated_data)

    def _get_create_save_kwargs(self, serializer) -> dict:
        """Формирует служебные поля создаваемого контента."""
        artist = self._get_managed_artist(serializer)

        save_kwargs = {
            'created_by': self.request.user,
        }

        model = serializer.Meta.model

        try:
            model._meta.get_field('artist')
        except FieldDoesNotExist:
            pass
        else:
            save_kwargs.update({
                'artist': artist,
                'payout_recipient': artist.default_payout_recipient,
            })

        return save_kwargs

    def perform_create(self, serializer):
        with transaction.atomic():
            save_kwargs = self._get_create_save_kwargs(serializer)
            instance = serializer.save(**save_kwargs)
            self._update_product_data(instance, serializer.validated_data)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._update_product_data(instance, serializer.validated_data)
