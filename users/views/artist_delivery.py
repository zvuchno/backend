from rest_framework import status, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.permissions import IsArtistOrLabel

from users.models import (
    ArtistShippingPoint,
    ArtistStoreSettings,
)
from users.schemas import (
    artist_pickup_point_schema,
    artist_shipping_point_schema,
)
from users.schemas.artist_delivery import (
    managed_artist_pickup_point_schema,
    managed_artist_shipping_point_schema,
)
from users.serializers import (
    ArtistPickupSettingsSerializer,
    ArtistShippingSettingsSerializer,
)
from users.views.mixins import ManagedArtistProfileMixin


@artist_pickup_point_schema
class ArtistPickupPointBaseViewSet(
    ManagedArtistProfileMixin,
    viewsets.ViewSet,
):
    """Управление настройками самовывоза доступного профиля."""

    permission_classes = (IsArtistOrLabel,)
    http_method_names = ('get', 'post')

    def list(self, request, *args, **kwargs):
        """Возвращает точки и общее состояние самовывоза."""
        artist = self.get_artist_profile()

        serializer = ArtistPickupSettingsSerializer(
            artist,
        )

        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Сохраняет изменения точек и состояние самовывоза."""
        artist = self.get_artist_profile()

        serializer = ArtistPickupSettingsSerializer(
            artist,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


@artist_pickup_point_schema
class ArtistPickupPointViewSet(ArtistPickupPointBaseViewSet):
    """Управление своим самовывозом."""


@managed_artist_pickup_point_schema
class ManagedArtistPickupPointViewSet(
    ArtistPickupPointBaseViewSet,
):
    """Управление самовывозом управляемого профиля."""


@artist_shipping_point_schema
class ArtistShippingPointBaseView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Управление ПВЗ отправления доступного профиля."""

    permission_classes = (IsArtistOrLabel,)
    serializer_class = ArtistShippingSettingsSerializer
    http_method_names = ('get', 'put', 'delete')
    pagination_class = None

    def get(self, request, *args, **kwargs):
        """Возвращает ПВЗ и состояние доставки СДЭК."""
        artist = self.get_artist_profile()

        serializer = self.get_serializer(artist)

        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        """Сохраняет ПВЗ и состояние доставки СДЭК."""
        artist = self.get_artist_profile()

        serializer = self.get_serializer(
            artist,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        """Удаляет ПВЗ и выключает доставку СДЭК."""
        artist = self.get_artist_profile()

        ArtistShippingPoint.objects.filter(
            artist=artist,
        ).delete()

        ArtistStoreSettings.objects.filter(
            artist=artist,
            shipping_enabled=True,
        ).update(
            shipping_enabled=False,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


@artist_shipping_point_schema
class ArtistShippingPointView(ArtistShippingPointBaseView):
    """Управление собственным ПВЗ отправления."""


@managed_artist_shipping_point_schema
class ManagedArtistShippingPointView(
    ArtistShippingPointBaseView,
):
    """Управление ПВЗ отправления управляемого профиля."""
