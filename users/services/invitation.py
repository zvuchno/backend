import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import ValidationError

from common.utils import normalize_email
from common.utils.urls import build_frontend_url

from config import settings
from users.models import (
    ArtistProfile,
    ArtistProfileClaimInvitation,
    ArtistProfileType,
    TokenInvitation,
    TokenInvitationStatus,
)
from users.services import (
    send_artist_profile_claim_accepted_mail,
    send_artist_profile_claim_invitation_mail,
    send_artist_profile_claim_rejected_mail,
)

User = get_user_model()

INVITATION_TOKEN_BYTES = 32
INVITATION_TTL_DAYS = 7


def build_artist_profile_claim_url(token: str) -> str:
    """Строит ссылку для перехода к приглашению артиста."""
    return build_frontend_url(
        settings.FRONTEND_ARTIST_CLAIM_PATH,
        {
            'token': token,
        },
    )


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
    ) -> ArtistProfileClaimInvitation:
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

        transaction.on_commit(
            lambda: send_artist_profile_claim_invitation_mail(
                to_email=email,
                artist_name=artist.name,
                label_name=artist.label.name,
                invitation_url=build_artist_profile_claim_url(raw_token),
            ),
        )

        return claim

    @classmethod
    @transaction.atomic
    def accept(
        cls,
        *,
        token: str,
        user,
    ) -> ArtistProfileClaimInvitation:
        """Принимает приглашение на управление профилем артиста."""
        invitation = (
            TokenInvitation.objects
            .select_for_update()
            .select_related('artist_profile_claim')
            .get(
                token_hash=hash_invitation_token(token),
            )
        )

        now = timezone.now()

        if invitation.expires_at <= now:
            raise ValidationError({
                'detail': 'Срок действия приглашения истёк.',
            })

        if invitation.status != TokenInvitationStatus.PENDING:
            raise ValidationError({
                'status': (
                    f'Приглашение уже имеет статус '
                    f'«{invitation.get_status_display()}».'
                ),
            })

        if normalize_email(invitation.recipient_email) != normalize_email(
            user.email,
        ):
            raise ValidationError({
                'email': 'Нельзя принять приглашение этим аккаунтом.',
            })

        artist = ArtistProfile.objects.select_for_update().get(
            pk=invitation.artist_profile_claim.artist_id,
        )

        if artist.user_id is not None:
            raise ValidationError({
                'detail': 'У профиля уже есть собственный аккаунт.',
            })

        if ArtistProfile.objects.filter(user=user).exists():
            raise ValidationError({
                'detail': 'Уже есть собственный профиль артиста.',
            })

        artist.user = user
        artist.save(update_fields=('user',))

        invitation.status = TokenInvitationStatus.ACCEPTED
        invitation.responded_by = user
        invitation.responded_at = now
        invitation.save(
            update_fields=(
                'status',
                'responded_by',
                'responded_at',
                'updated_at',
            ),
        )

        transaction.on_commit(
            lambda: send_artist_profile_claim_accepted_mail(
                to_email=invitation.created_by.email,
                artist_name=artist.name,
                recipient_email=user.email,
            ),
        )

        return invitation.artist_profile_claim

    @classmethod
    @transaction.atomic
    def reject(
        cls,
        *,
        token: str,
        user,
    ) -> ArtistProfileClaimInvitation:
        """Отклоняет приглашение на управление профилем артиста."""
        invitation = (
            TokenInvitation.objects
            .select_for_update()
            .select_related(
                'artist_profile_claim__artist__label',
            )
            .get(
                token_hash=hash_invitation_token(token),
            )
        )

        now = timezone.now()

        if invitation.expires_at <= now:
            raise ValidationError({
                'detail': 'Срок действия приглашения истёк.',
            })

        if invitation.status != TokenInvitationStatus.PENDING:
            raise ValidationError({
                'status': (
                    f'Приглашение уже имеет статус '
                    f'«{invitation.get_status_display()}».'
                ),
            })

        if normalize_email(invitation.recipient_email) != normalize_email(
            user.email,
        ):
            raise ValidationError({
                'email': 'Нельзя отклонить приглашение этим аккаунтом.',
            })

        invitation.status = TokenInvitationStatus.REJECTED
        invitation.responded_by = user
        invitation.responded_at = now
        invitation.save(
            update_fields=(
                'status',
                'responded_by',
                'responded_at',
                'updated_at',
            ),
        )

        claim = invitation.artist_profile_claim

        transaction.on_commit(
            lambda: send_artist_profile_claim_rejected_mail(
                to_email=invitation.created_by.email,
                artist_name=claim.artist.name,
                recipient_email=invitation.recipient_email,
            ),
        )

        return claim

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
