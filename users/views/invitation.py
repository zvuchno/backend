from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsLabel

from users.schemas import (
    artist_profile_claim_invitation_accept_schema,
    artist_profile_claim_invitation_create_schema,
    artist_profile_claim_invitation_read_schema,
    artist_profile_claim_invitation_reject_schema,
    artist_profile_claim_invitation_resend_schema,
    artist_profile_claim_invitation_revoke_schema,
)
from users.serializers import (
    ArtistProfileClaimInvitationCreateSerializer,
    ArtistProfileClaimInvitationReadSerializer,
    ArtistProfileClaimInvitationResendSerializer,
    ArtistProfileClaimInvitationSerializer,
    ArtistProfileClaimInvitationTokenSerializer,
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


@artist_profile_claim_invitation_read_schema
class ArtistProfileClaimInvitationView(GenericAPIView):
    """Представление для просмотра приглашения получателем."""

    permission_classes = (AllowAny,)
    serializer_class = ArtistProfileClaimInvitationReadSerializer

    def get(self, request, *args, **kwargs):
        token = request.query_params.get('token')

        if not token:
            raise ValidationError({
                'token': 'Укажите токен приглашения.',
            })

        claim = ArtistProfileClaimInvitationService.get_by_token(token)

        return Response(
            self.get_serializer(claim).data,
        )


@artist_profile_claim_invitation_accept_schema
class ArtistProfileClaimInvitationAcceptView(GenericAPIView):
    """Представление для принятия приглашения."""

    permission_classes = (IsAuthenticated,)
    serializer_class = ArtistProfileClaimInvitationTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        claim = ArtistProfileClaimInvitationService.accept(
            token=serializer.validated_data['token'],
            user=request.user,
        )

        return Response(
            ArtistProfileClaimInvitationSerializer(claim).data,
        )


@artist_profile_claim_invitation_reject_schema
class ArtistProfileClaimInvitationRejectView(GenericAPIView):
    """Представление для отклонения приглашения."""

    permission_classes = (AllowAny,)
    serializer_class = ArtistProfileClaimInvitationTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        claim = ArtistProfileClaimInvitationService.reject(
            token=serializer.validated_data['token'],
        )

        return Response(
            ArtistProfileClaimInvitationSerializer(claim).data,
        )


@artist_profile_claim_invitation_resend_schema
class ArtistProfileClaimInvitationResendView(
    ManagedArtistProfileMixin,
    GenericAPIView,
):
    """Представление для повторной отправки приглашения."""

    permission_classes = (IsLabel,)
    serializer_class = ArtistProfileClaimInvitationResendSerializer

    def post(self, request, *args, **kwargs):
        artist = self.get_artist_profile()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        claim = ArtistProfileClaimInvitationService.resend(
            artist=artist,
            actor=request.user,
            email=serializer.validated_data.get('email'),
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
