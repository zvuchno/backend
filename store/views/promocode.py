"""ViewSet для работы с моделью Promocode."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.response import Response

from common.access import managed_artist_q
from common.permissions import (
    IsArtistOrLabel,
    IsStoreObjectManager,
)

from .mixins import (
    ManagedArtistActionMixin,
    SoftDeleteMixin,
)
from store.filters import PromoCodeFilter
from store.models import Promocode
from store.schema import promocode_schema
from store.serializers import (
    PromocodeReadDetailSerializer,
    PromocodeReadSerializer,
    PromocodeWriteSerializer,
)


@promocode_schema
class PromocodeViewSet(
    ManagedArtistActionMixin,
    SoftDeleteMixin,
    viewsets.ModelViewSet,
):
    """API для работы с промокодами.

    Промокод может создать только артист.
    Артист видит и управляет только своими промокодами.
    """

    queryset = Promocode.objects.all()
    permission_classes = (IsArtistOrLabel, IsStoreObjectManager)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = PromoCodeFilter

    def get_queryset(self):
        return Promocode.objects.filter(
            managed_artist_q(self.request.user),
        ).select_related('artist', 'created_by')

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
        artist = self._get_managed_artist(serializer)

        serializer.save(
            artist=artist,
            created_by=self.request.user,
        )
