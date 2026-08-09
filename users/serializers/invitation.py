from rest_framework import serializers

from users.models import ArtistProfileClaimInvitation


class ArtistProfileClaimInvitationCreateSerializer(
    serializers.Serializer,
):
    """Сериализатор создания инвайта."""

    email = serializers.EmailField()


class ArtistProfileClaimInvitationSerializer(serializers.ModelSerializer):
    """Сериализатор инвайтов."""

    email = serializers.EmailField(
        source='invitation.recipient_email',
    )
    status = serializers.CharField(
        source='invitation.status',
    )
    created_at = serializers.DateTimeField(
        source='invitation.created_at',
    )
    expires_at = serializers.DateTimeField(
        source='invitation.expires_at',
    )

    class Meta:
        model = ArtistProfileClaimInvitation
        fields = (
            'email',
            'status',
            'created_at',
            'expires_at',
        )
