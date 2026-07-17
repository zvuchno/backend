"""Миксины вьюсетов."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.access import can_manage_artist

from store.services import ProductService
from users.models import ArtistProfile


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

    def _resolve_create_artist(self, serializer) -> ArtistProfile:
        """Определяет артиста создаваемого контента."""
        validated_data = serializer.validated_data

        album = validated_data.get('album')
        if album is not None:
            return album.artist

        artist = validated_data.get('artist')
        if artist is not None:
            return artist

        profile = getattr(
            self.request.user,
            'artist_profile',
            None,
        )

        if profile is None:
            raise ValidationError({
                'artist': 'Необходимо указать артиста.',
            })

        return profile

    def _get_create_save_kwargs(self, serializer) -> dict:
        """Формирует служебные поля создаваемого контента."""
        artist = self._resolve_create_artist(serializer)

        if not can_manage_artist(
            self.request.user,
            artist,
        ):
            raise PermissionDenied(
                'У вас нет прав создавать контент этого артиста.',
            )

        save_kwargs = {
            'created_by': self.request.user,
        }

        model = serializer.Meta.model

        if hasattr(model, 'artist'):
            save_kwargs.update({
                'artist': artist,
                'payout_recipient': (artist.default_payout_recipient),
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
