"""Схемы OpenAPI для приглашений на управление профилем артиста."""

from drf_spectacular.utils import extend_schema

from users.serializers import (
    ArtistProfileClaimInvitationCreateSerializer,
    ArtistProfileClaimInvitationSerializer,
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
    request=None,
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
