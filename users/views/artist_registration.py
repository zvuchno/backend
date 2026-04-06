from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response

from .base_registration import BaseRegistrationView
from users.schemas import artist_registration_schema
from users.serializers import (
    ArtistRegistrationSerializer,
    BecomeArtistSerializer,
)


@artist_registration_schema
class ArtistRegistrationView(BaseRegistrationView):
    """Представление для регистрации артиста."""

    serializer_class = ArtistRegistrationSerializer
    permission_classes = [AllowAny]


class BecomeArtistView(GenericAPIView):
    """Представление для создания профиля артиста существующим слушателем."""

    serializer_class = BecomeArtistSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artist = serializer.save(user=request.user)
        response_serializer = self.get_serializer(artist)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )
