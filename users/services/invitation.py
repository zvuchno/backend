import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import ValidationError

from common.utils import normalize_email

from users.models import (
    ArtistProfile,
    ArtistProfileClaimInvitation,
    ArtistProfileType,
    TokenInvitation,
    TokenInvitationStatus,
)

User = get_user_model()

INVITATION_TOKEN_BYTES = 32
INVITATION_TTL_DAYS = 7


def generate_invitation_token() -> str:
    """Генерирует одноразовый токен приглашения."""
    return secrets.token_urlsafe(INVITATION_TOKEN_BYTES)


def hash_invitation_token(token: str) -> str:
    """Возвращает хеш токена приглашения."""
    return hashlib.sha256(token.encode()).hexdigest()


class ArtistProfileClaimInvitationService:
    """Сервис приглашений на управление профилем артиста."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        artist: ArtistProfile,
        email: str,
        created_by,
    ) -> tuple[ArtistProfileClaimInvitation, str]:
        """Создаёт приглашение на управление профилем артиста."""
        email = normalize_email(email)

        cls._validate_artist(
            artist=artist,
            created_by=created_by,
        )
        cls._validate_email(email)
        cls._validate_pending_claim(artist)

        raw_token = generate_invitation_token()

        invitation = TokenInvitation.objects.create(
            recipient_email=email,
            token_hash=hash_invitation_token(raw_token),
            created_by=created_by,
            expires_at=timezone.now() + timedelta(days=INVITATION_TTL_DAYS),
        )

        claim = ArtistProfileClaimInvitation.objects.create(
            invitation=invitation,
            artist=artist,
        )

        return claim, raw_token

    @staticmethod
    @transaction.atomic
    def accept(self, token: str, user) -> ArtistProfileClaimInvitation:
        """Принятие инвайта."""
        invitation = (
            TokenInvitation.objects
            .select_for_update()
            .select_related('artist_profile_claim__artist')
            .get(token_hash=hash_invitation_token(token))
        )

        if invitation.expires_at < timezone.now():
            raise ValidationError({
                'detail': 'Приглашение более не действительно.',
            })
        if invitation.status != TokenInvitationStatus.PENDING:
            raise ValidationError({
                'status': f'Приглашение {invitation.get_status_display()}',
            })

    @staticmethod
    def _validate_artist(
        *,
        artist: ArtistProfile,
        created_by,
    ) -> None:
        """Проверяет возможность пригласить пользователя к профилю."""
        if artist.profile_type != ArtistProfileType.ARTIST:
            raise ValidationError({
                'artist': 'Приглашение доступно только для профиля артиста.',
            })

        if artist.user_id is not None:
            raise ValidationError({
                'artist': 'У профиля артиста уже есть собственный аккаунт.',
            })

        if artist.label_id is None:
            raise ValidationError({
                'artist': 'Профиль артиста не связан с лейблом.',
            })

        if artist.label.user_id != created_by.id:
            raise PermissionDenied(
                'Вы не управляете лейблом этого артиста.',
            )

    @staticmethod
    def _validate_email(email: str) -> None:
        """Проверяет возможность отправить приглашение на email."""
        if User.objects.filter(email=email).exists():
            raise ValidationError({
                'email': 'Пользователь с таким email уже зарегистрирован.',
            })

    @staticmethod
    def _validate_pending_claim(
        artist: ArtistProfile,
    ) -> None:
        """Проверяет отсутствие активного приглашения на профиль."""
        now = timezone.now()

        TokenInvitation.objects.filter(
            artist_profile_claim__artist=artist,
            status=TokenInvitationStatus.PENDING,
            expires_at__lte=now,
        ).update(
            status=TokenInvitationStatus.EXPIRED,
        )

        if ArtistProfileClaimInvitation.objects.filter(
            artist=artist,
            invitation__status=TokenInvitationStatus.PENDING,
            invitation__expires_at__gt=now,
        ).exists():
            raise ValidationError({
                'artist': ('Для профиля уже существует активное приглашение.'),
            })
