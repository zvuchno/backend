"""ViewSet для работы с моделью Promocode."""

from rest_framework import viewsets

from common.permissions import IsArtist, IsStoreObjectOwner

from store.models import Promocode
from store.schema import promocode_schema
from store.serializers import PromocodeSerializer


@promocode_schema
class PromocodeViewSet(viewsets.ModelViewSet):
    """API для работы с промокодами.

    Промокод может создать только артист.
    Артист видит и управляет только своими промокодами.
    """

    serializer_class = PromocodeSerializer
    permission_classes = (IsArtist, IsStoreObjectOwner)

    def get_queryset(self):
        return Promocode.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
