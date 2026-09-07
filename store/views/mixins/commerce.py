"""Миксины вьюсетов."""

from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from rest_framework.exceptions import ValidationError

from common.services import get_artist_publication_readiness

from store.models import Album, Merch
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
        model = serializer.Meta.model

        self._validate_publication_readiness(
            model=model,
            artist=artist,
            validated_data=serializer.validated_data,
        )

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
            instance = serializer.instance

            self._validate_publication_readiness(
                model=type(instance),
                artist=instance.artist,
                validated_data=serializer.validated_data,
            )

            instance = serializer.save()
            self._update_product_data(instance, serializer.validated_data)

    def _validate_publication_readiness(
        self,
        *,
        model,
        artist,
        validated_data,
    ) -> None:
        """Проверяет готовность артиста к публикации контента."""
        if validated_data.get('is_published') is not True:
            return

        if model not in (Album, Merch):
            return

        readiness = get_artist_publication_readiness(artist)

        if model is Merch:
            can_publish = readiness.can_publish_physical
            missing = readiness.physical_missing
        else:
            can_publish = readiness.can_publish_digital
            missing = readiness.digital_missing

        if not can_publish:
            raise ValidationError({
                'is_published': [requirement.value for requirement in missing],
            })
