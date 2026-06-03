"""ViewSet для работы с моделью Promocode."""

from rest_framework import status, viewsets
from rest_framework.response import Response

from common.permissions import IsArtist, IsStoreObjectOwner

from .mixins import SoftDeleteMixin
from store.models import Promocode
from store.schema import promocode_schema
from store.serializers import (
    PromocodeReadDetailSerializer,
    PromocodeReadSerializer,
    PromocodeWriteSerializer,
)


@promocode_schema
class PromocodeViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """API для работы с промокодами.

    Промокод может создать только артист.
    Артист видит и управляет только своими промокодами.
    """

    permission_classes = (IsArtist, IsStoreObjectOwner)
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_queryset(self):
        return Promocode.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return PromocodeWriteSerializer
        if self.action == 'retrieve':
            return PromocodeReadDetailSerializer
        return PromocodeReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        read_serializer = PromocodeReadDetailSerializer(serializer.instance)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        read_serializer = PromocodeReadDetailSerializer(instance)
        return Response(read_serializer.data)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
