from rest_framework import serializers

from users.models import ArtistProfileClaimInvitation


class ArtistProfileClaimInvitationCreateSerializer(
    serializers.Serializer,
):
    """Сериализатор создания инвайта."""

    email = serializers.EmailField()


class ArtistProfileClaimInvitationResendSerializer(
    serializers.Serializer,
):
    """Сериализатор повторной отправки приглашения."""

    email = serializers.EmailField(required=False)


class ArtistProfileClaimInvitationTokenSerializer(
    serializers.Serializer,
):
    """Сериализатор токена приглашения."""

    token = serializers.CharField()


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


class ArtistProfileClaimInvitationReadSerializer(
    serializers.ModelSerializer,
):
    """Сериализатор просмотра приглашения получателем."""

    artist_id = serializers.IntegerField(
        source='artist.id',
    )
    artist_name = serializers.CharField(
        source='artist.name',
    )
    label_id = serializers.IntegerField(
        source='artist.label.id',
    )
    label_name = serializers.CharField(
        source='artist.label.name',
    )
    status = serializers.CharField(
        source='invitation.status',
    )
    expires_at = serializers.DateTimeField(
        source='invitation.expires_at',
    )

    class Meta:
        model = ArtistProfileClaimInvitation
        fields = (
            'artist_id',
            'artist_name',
            'label_id',
            'label_name',
            'status',
            'expires_at',
        )
