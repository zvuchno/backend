import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import ValidationError

from common.utils import normalize_email
from common.utils.urls import build_frontend_url

from .email import (
    send_artist_profile_claim_accepted_mail,
    send_artist_profile_claim_invitation_mail,
    send_artist_profile_claim_rejected_mail,
)
from users.models import (
    ArtistProfile,
    ArtistProfileClaimInvitation,
    ArtistProfileType,
    TokenInvitation,
    TokenInvitationStatus,
)

User = get_user_model()

INVITATION_TOKEN_BYTES = 32


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
        artist = (
            ArtistProfile.objects
            .select_for_update()
            .select_related('label')
            .get(pk=artist.pk)
        )

        cls._validate_artist(
            artist=artist,
            created_by=created_by,
        )
        cls._validate_email(email)
        cls._validate_claim_not_exists(artist)

        raw_token = generate_invitation_token()

        invitation = TokenInvitation.objects.create(
            recipient_email=email,
            token_hash=hash_invitation_token(raw_token),
            created_by=created_by,
            expires_at=timezone.now()
            + timedelta(
                days=settings.INVITATION_TTL_DAYS,
            ),
        )

        claim = ArtistProfileClaimInvitation.objects.create(
            invitation=invitation,
            artist=artist,
        )

        cls._send_invitation_after_commit(
            invitation=invitation,
            artist=artist,
            raw_token=raw_token,
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
        invitation = cls._get_pending_invitation(
            token=token,
            user=user,
        )

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

        cls._set_response(
            invitation=invitation,
            status=TokenInvitationStatus.ACCEPTED,
            user=user,
        )

        to_email = invitation.created_by.email
        artist_name = artist.name
        recipient_email = user.email
        transaction.on_commit(
            lambda: send_artist_profile_claim_accepted_mail(
                to_email=to_email,
                artist_name=artist_name,
                recipient_email=recipient_email,
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
        invitation = cls._get_pending_invitation(
            token=token,
            user=user,
        )

        cls._set_response(
            invitation=invitation,
            status=TokenInvitationStatus.REJECTED,
            user=user,
        )

        claim = invitation.artist_profile_claim

        to_email = invitation.created_by.email
        artist_name = claim.artist.name
        recipient_email = invitation.recipient_email

        transaction.on_commit(
            lambda: send_artist_profile_claim_rejected_mail(
                to_email=to_email,
                artist_name=artist_name,
                recipient_email=recipient_email,
            ),
        )

        return claim

    @classmethod
    @transaction.atomic
    def resend(
        cls,
        *,
        artist: ArtistProfile,
        actor,
    ) -> ArtistProfileClaimInvitation:
        """Повторно отправляет приглашение на управление профилем артиста."""
        cls._validate_label(
            artist=artist,
            actor=actor,
        )

        claim = cls._get_latest_claim(artist)
        invitation = claim.invitation

        if artist.user_id is not None:
            raise ValidationError({
                'detail': 'У профиля уже есть собственный аккаунт.',
            })

        if invitation.status == TokenInvitationStatus.ACCEPTED:
            raise ValidationError({
                'detail': 'Приглашение уже принято.',
            })

        raw_token = cls._renew_invitation(invitation)

        cls._send_invitation_after_commit(
            invitation=invitation,
            artist=artist,
            raw_token=raw_token,
        )

        return claim

    @classmethod
    @transaction.atomic
    def revoke(
        cls,
        *,
        artist: ArtistProfile,
        actor,
    ) -> ArtistProfileClaimInvitation:
        """Отзывает приглашение на управление профилем артиста."""
        cls._validate_label(
            artist=artist,
            actor=actor,
        )

        claim = cls._get_latest_claim(artist)
        invitation = claim.invitation

        if invitation.status == TokenInvitationStatus.ACCEPTED:
            raise ValidationError({
                'detail': 'Принятое приглашение нельзя отозвать.',
            })

        if invitation.status != TokenInvitationStatus.PENDING:
            raise ValidationError({
                'detail': 'Можно отозвать только активное приглашение.',
            })

        invitation.status = TokenInvitationStatus.REVOKED
        invitation.save(
            update_fields=(
                'status',
                'updated_at',
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
    def _validate_label(
        *,
        artist: ArtistProfile,
        actor,
    ) -> None:
        """Проверяет право пользователя управлять приглашением."""
        if artist.label_id is None:
            raise ValidationError({
                'artist': 'Профиль артиста не связан с лейблом.',
            })

        if artist.label.user_id != actor.id:
            raise PermissionDenied(
                'Вы не управляете лейблом этого артиста.',
            )
        if artist.profile_type != ArtistProfileType.ARTIST:
            raise ValidationError({
                'artist': 'Операция доступна только для профиля артиста.',
            })

    @staticmethod
    def _validate_email(email: str) -> None:
        """Проверяет возможность отправить приглашение на email."""
        if User.objects.filter(email=email).exists():
            raise ValidationError({
                'email': 'Пользователь с таким email уже зарегистрирован.',
            })

    @staticmethod
    def _validate_claim_not_exists(
        artist: ArtistProfile,
    ) -> None:
        """Проверяет отсутствие ранее созданного приглашения."""
        if ArtistProfileClaimInvitation.objects.filter(
            artist=artist,
        ).exists():
            raise ValidationError({
                'artist': (
                    'Для профиля уже создавалось приглашение. '
                    'Используйте повторную отправку.'
                ),
            })

    @classmethod
    def _get_pending_invitation(
        cls,
        *,
        token: str,
        user,
    ) -> TokenInvitation:
        """Возвращает доступное пользователю активное приглашение."""
        invitation = (
            TokenInvitation.objects
            .select_for_update()
            .select_related('artist_profile_claim', 'created_by')
            .get(
                token_hash=hash_invitation_token(token),
            )
        )

        if invitation.expires_at <= timezone.now():
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
                'email': 'Нельзя использовать приглашение этим аккаунтом.',
            })

        return invitation

    @staticmethod
    def _set_response(
        *,
        invitation: TokenInvitation,
        status: TokenInvitationStatus,
        user,
    ) -> None:
        """Фиксирует ответ пользователя на приглашение."""
        invitation.status = status
        invitation.responded_by = user
        invitation.responded_at = timezone.now()
        invitation.save(
            update_fields=(
                'status',
                'responded_by',
                'responded_at',
                'updated_at',
            ),
        )

    @staticmethod
    def _get_latest_claim(
        artist: ArtistProfile,
    ) -> ArtistProfileClaimInvitation:
        """Возвращает последнее приглашение профиля артиста."""
        claim = (
            ArtistProfileClaimInvitation.objects
            .select_for_update(of=('self', 'invitation'))
            .select_related('invitation')
            .filter(artist=artist)
            .order_by('-invitation__created_at')
            .first()
        )

        if claim is None:
            raise ValidationError({
                'detail': 'Для профиля ещё не создавалось приглашение.',
            })

        return claim

    @staticmethod
    def _renew_invitation(
        invitation: TokenInvitation,
    ) -> str:
        """Перевыпускает токен приглашения и продлевает срок действия."""
        raw_token = generate_invitation_token()

        invitation.token_hash = hash_invitation_token(raw_token)
        invitation.status = TokenInvitationStatus.PENDING
        invitation.expires_at = timezone.now() + timedelta(
            days=settings.INVITATION_TTL_DAYS,
        )
        invitation.responded_by = None
        invitation.responded_at = None

        invitation.save(
            update_fields=(
                'token_hash',
                'status',
                'expires_at',
                'responded_by',
                'responded_at',
                'updated_at',
            ),
        )

        return raw_token

    @staticmethod
    def _send_invitation_after_commit(
        *,
        invitation: TokenInvitation,
        artist: ArtistProfile,
        raw_token: str,
    ) -> None:
        """Планирует отправку письма с приглашением после коммита."""
        to_email = invitation.recipient_email
        artist_name = artist.name
        label_name = artist.label.name
        invitation_url = build_artist_profile_claim_url(raw_token)

        transaction.on_commit(
            lambda: send_artist_profile_claim_invitation_mail(
                to_email=to_email,
                artist_name=artist_name,
                label_name=label_name,
                invitation_url=invitation_url,
            ),
        )
