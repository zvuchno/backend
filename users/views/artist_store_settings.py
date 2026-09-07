from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsArtistOrLabel

from users.schemas import (
    artist_store_settings_schema,
    managed_artist_store_settings_schema,
)
from users.serializers import ArtistStoreSettingsSerializer
from users.views.mixins import ManagedArtistProfileMixin


class ArtistStoreSettingsBaseView(
    ManagedArtistProfileMixin,
    APIView,
):
    """Управление настройками магазина доступного профиля."""

    permission_classes = (IsArtistOrLabel,)

    def get(self, request, *args, **kwargs):
        """Возвращает собственные настройки магазина профиля."""
        artist = self.get_artist_profile()
        settings = getattr(artist, 'store_settings', None)

        if settings is None:
            return Response(None, status=status.HTTP_200_OK)

        serializer = ArtistStoreSettingsSerializer(settings)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        """Создаёт или полностью обновляет настройки магазина профиля."""
        artist = self.get_artist_profile()
        settings = getattr(artist, 'store_settings', None)

        serializer = ArtistStoreSettingsSerializer(
            settings,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        if settings is None:
            serializer.save(artist=artist)
            response_status = status.HTTP_201_CREATED
        else:
            serializer.save()
            response_status = status.HTTP_200_OK

        return Response(serializer.data, status=response_status)


@artist_store_settings_schema
class ArtistStoreSettingsView(ArtistStoreSettingsBaseView):
    """Управление настройками магазина собственного профиля."""


@managed_artist_store_settings_schema
class ManagedArtistStoreSettingsView(ArtistStoreSettingsBaseView):
    """Управление настройками магазина управляемого профиля."""
