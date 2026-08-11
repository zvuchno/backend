"""Схемы OpenAPI для приглашений на управление профилем артиста."""

from drf_spectacular.utils import OpenApiParameter, extend_schema

from users.serializers import (
    ArtistProfileClaimInvitationCreateSerializer,
    ArtistProfileClaimInvitationReadSerializer,
    ArtistProfileClaimInvitationSerializer,
    ArtistProfileClaimInvitationTokenSerializer,
)

artist_profile_claim_invitation_create_schema = extend_schema(
    tags=['Label: managed profiles'],
    summary='Пригласить пользователя к управлению профилем артиста',
    description=(
        'Создаёт приглашение для выбранного управляемого профиля артиста '
        'и отправляет ссылку на указанный email.'
    ),
    request=ArtistProfileClaimInvitationCreateSerializer,
    responses={
        201: ArtistProfileClaimInvitationSerializer,
    },
)


artist_profile_claim_invitation_resend_schema = extend_schema(
    tags=['Label: managed profiles'],
    summary='Повторно отправить приглашение',
    description=(
        'Перевыпускает токен существующего приглашения, продлевает срок '
        'его действия и повторно отправляет письмо получателю.'
    ),
    responses={
        200: ArtistProfileClaimInvitationSerializer,
    },
)


artist_profile_claim_invitation_revoke_schema = extend_schema(
    tags=['Label: managed profiles'],
    summary='Отозвать приглашение',
    description=(
        'Отзывает активное приглашение на управление выбранным '
        'профилем артиста.'
    ),
    request=None,
    responses={
        200: ArtistProfileClaimInvitationSerializer,
    },
)


artist_profile_claim_invitation_read_schema = extend_schema(
    tags=['Invitations'],
    summary='Получить информацию о приглашении',
    parameters=[
        OpenApiParameter(
            name='token',
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Токен приглашения.',
        ),
    ],
    responses={
        200: ArtistProfileClaimInvitationReadSerializer,
    },
)


artist_profile_claim_invitation_accept_schema = extend_schema(
    tags=['Invitations'],
    summary='Принять приглашение',
    request=ArtistProfileClaimInvitationTokenSerializer,
    responses={
        200: ArtistProfileClaimInvitationSerializer,
    },
)


artist_profile_claim_invitation_reject_schema = extend_schema(
    tags=['Invitations'],
    summary='Отклонить приглашение',
    request=ArtistProfileClaimInvitationTokenSerializer,
    responses={
        200: ArtistProfileClaimInvitationSerializer,
    },
)
