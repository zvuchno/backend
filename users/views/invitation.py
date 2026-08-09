from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.permissions import IsArtistOrLabel, IsLabel

from users.serializers import (
    ArtistProfileClaimInvitationCreateSerializer,
    ArtistProfileClaimInvitationSerializer,
)
from users.services.invitation import ArtistProfileClaimInvitationService
from users.views.mixins import ManagedArtistProfileMixin


class ArtistProfileClaimInvitationCreateView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Представление для создания инвайта к управлению артистом."""

    permission_classes = (IsArtistOrLabel,)
    serializer_class = ArtistProfileClaimInvitationCreateSerializer

    def post(self, request, *args, **kwargs):
        artist = self.get_artist_profile()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        claim = ArtistProfileClaimInvitationService.create(
            artist=artist,
            email=serializer.validated_data['email'],
            created_by=request.user,
        )

        return Response(
            ArtistProfileClaimInvitationSerializer(claim).data,
            status=status.HTTP_201_CREATED,
        )


class ArtistProfileClaimInvitationResendView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Представление для повторной отправки приглашения."""

    permission_classes = (IsArtistOrLabel,)

    def post(self, request, *args, **kwargs):
        artist = self.get_artist_profile()

        claim = ArtistProfileClaimInvitationService.resend(
            artist=artist,
            actor=request.user,
        )

        return Response(
            ArtistProfileClaimInvitationSerializer(claim).data,
        )


class ArtistProfileClaimInvitationRevokeView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Представление для отзыва инвайта."""

    permission_classes = (IsLabel,)

    def delete(self, request, *args, **kwargs):
        artist = self.get_artist_profile()

        claim = ArtistProfileClaimInvitationService.revoke(
            artist=artist,
            actor=request.user,
        )

        return Response(
            ArtistProfileClaimInvitationSerializer(claim).data,
        )
