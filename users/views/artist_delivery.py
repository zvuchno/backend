from rest_framework import status, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.permissions import IsArtistOrLabel

from users.models import ArtistPickupPoint, ArtistShippingPoint
from users.serializers import (
    ArtistPickupPointManageSerializer,
    ArtistShippingPointSerializer,
)
from users.views.mixins import ManagedArtistProfileMixin


class ArtistPickupPointViewSet(
    ManagedArtistProfileMixin,
    viewsets.ModelViewSet,
):
    """Управление точками самовывоза выбранного профиля."""

    permission_classes = (IsArtistOrLabel,)
    serializer_class = ArtistPickupPointManageSerializer
    http_method_names = ('get', 'post', 'patch', 'delete')
    pagination_class = None

    def get_queryset(self):
        """Возвращает точки самовывоза выбранного профиля."""
        return ArtistPickupPoint.objects.filter(
            artist=self.get_artist_profile(),
        ).order_by('id')

    def perform_create(self, serializer):
        """Создаёт точку самовывоза выбранного профиля."""
        serializer.save(
            artist=self.get_artist_profile(),
        )


class ArtistShippingPointView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Получение и настройка ПВЗ отправления выбранного профиля."""

    permission_classes = (IsArtistOrLabel,)
    serializer_class = ArtistShippingPointSerializer
    http_method_names = ('get', 'put', 'delete')
    pagination_class = None

    def get(self, request, *args, **kwargs):
        """Возвращает сохранённый ПВЗ отправления."""
        artist = self.get_artist_profile()

        try:
            shipping_point = artist.shipping_point
        except ArtistShippingPoint.DoesNotExist:
            return Response(None, status=status.HTTP_200_OK)

        serializer = self.get_serializer(shipping_point)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        """Создаёт или заменяет ПВЗ отправления."""
        artist = self.get_artist_profile()

        try:
            shipping_point = artist.shipping_point
        except ArtistShippingPoint.DoesNotExist:
            shipping_point = None

        # True если объекта не было, ответить 201
        created = shipping_point is None

        serializer = self.get_serializer(
            shipping_point,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(artist=artist)

        return Response(
            serializer.data,
            status=(
                status.HTTP_201_CREATED if created else status.HTTP_200_OK
            ),
        )

    def delete(self, request, *args, **kwargs):
        """Удаляет сохранённый ПВЗ отправления."""
        artist = self.get_artist_profile()

        try:
            shipping_point = artist.shipping_point
        except ArtistShippingPoint.DoesNotExist:
            pass
        else:
            shipping_point.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
