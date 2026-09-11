from rest_framework import status, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.permissions import IsArtistOrLabel

from users.models import (
    ArtistPickupPoint,
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
    ArtistPickupPointManageSerializer,
    ArtistPickupSettingsSerializer,
    ArtistShippingSettingsSerializer,
)
from users.views.mixins import ManagedArtistProfileMixin


@artist_pickup_point_schema
class ArtistPickupPointBaseViewSet(
    ManagedArtistProfileMixin,
    viewsets.ModelViewSet,
):
    """Управление точками самовывоза доступного профиля."""

    permission_classes = (IsArtistOrLabel,)
    serializer_class = ArtistPickupPointManageSerializer
    http_method_names = ('get', 'post', 'patch', 'delete')
    pagination_class = None

    def get_queryset(self):
        """Возвращает точки самовывоза выбранного профиля."""
        return ArtistPickupPoint.objects.filter(
            artist=self.get_artist_profile(),
        ).order_by('id')

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

    def perform_create(self, serializer):
        """Создаёт точку самовывоза выбранного профиля."""
        serializer.save(
            artist=self.get_artist_profile(),
        )

    def perform_update(self, serializer):
        """Обновляет точку и актуализирует состояние самовывоза."""
        pickup_point = serializer.save()

        self._disable_pickup_if_unavailable(
            pickup_point.artist,
        )

    def perform_destroy(self, instance):
        """Удаляет точку и актуализирует состояние самовывоза."""
        artist = instance.artist

        instance.delete()

        self._disable_pickup_if_unavailable(artist)

    @staticmethod
    def _disable_pickup_if_unavailable(artist) -> None:
        """Выключает самовывоз при отсутствии активных точек."""
        if artist.pickup_points.filter(is_active=True).exists():
            return

        ArtistStoreSettings.objects.filter(
            artist=artist,
            pickup_enabled=True,
        ).update(
            pickup_enabled=False,
        )


@artist_pickup_point_schema
class ArtistPickupPointViewSet(ArtistPickupPointBaseViewSet):
    """Управление своими точками самовывоза."""


@managed_artist_pickup_point_schema
class ManagedArtistPickupPointViewSet(
    ArtistPickupPointBaseViewSet,
):
    """Управление точками самовывоза управляемого профиля."""


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
