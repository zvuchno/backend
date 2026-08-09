from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.permissions import IsLabel

from users.schemas import (
    artist_profile_claim_invitation_create_schema,
    artist_profile_claim_invitation_resend_schema,
    artist_profile_claim_invitation_revoke_schema,
)
from users.serializers import (
    ArtistProfileClaimInvitationCreateSerializer,
    ArtistProfileClaimInvitationSerializer,
)
from users.services.invitation import ArtistProfileClaimInvitationService
from users.views.mixins import ManagedArtistProfileMixin


@artist_profile_claim_invitation_create_schema
class ArtistProfileClaimInvitationCreateView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Представление для создания инвайта к управлению артистом."""

    permission_classes = (IsLabel,)
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


@artist_profile_claim_invitation_resend_schema
class ArtistProfileClaimInvitationResendView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Представление для повторной отправки приглашения."""

    permission_classes = (IsLabel,)
    serializer_class = ArtistProfileClaimInvitationSerializer

    def post(self, request, *args, **kwargs):
        artist = self.get_artist_profile()

        claim = ArtistProfileClaimInvitationService.resend(
            artist=artist,
            actor=request.user,
        )

        return Response(
            ArtistProfileClaimInvitationSerializer(claim).data,
        )


@artist_profile_claim_invitation_revoke_schema
class ArtistProfileClaimInvitationRevokeView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Представление для отзыва инвайта."""

    permission_classes = (IsLabel,)
    serializer_class = ArtistProfileClaimInvitationSerializer

    def post(self, request, *args, **kwargs):
        artist = self.get_artist_profile()

        claim = ArtistProfileClaimInvitationService.revoke(
            artist=artist,
            actor=request.user,
        )

        return Response(
            ArtistProfileClaimInvitationSerializer(claim).data,
        )
