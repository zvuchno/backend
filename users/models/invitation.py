from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models.abstract import TimestampModel

from .artist import ArtistProfile


class TokenInvitationStatus(models.TextChoices):
    """Статусы приглашений."""

    PENDING = 'pending', 'Ожидает'
    ACCEPTED = 'accepted', 'Принято'
    REJECTED = 'rejected', 'Отклонено'
    REVOKED = 'revoked', 'Отозвано'
    EXPIRED = 'expired', 'Истекло'


class TokenInvitation(TimestampModel):
    """Внешнее приглашение с подтверждением с одноразовым токеном."""

    recipient_email = models.EmailField(
        'Email получателя',
    )
    token_hash = models.CharField(
        'Хеш токена',
        max_length=128,
        unique=True,
    )
    status = models.CharField(
        'Статус',
        max_length=16,
        choices=TokenInvitationStatus.choices,
        default=TokenInvitationStatus.PENDING,
    )
    send_count = models.PositiveIntegerField(
        'Количество отправок',
        default=0,
    )
    last_sent_at = models.DateTimeField(
        'Дата последней отправки',
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_token_invitations',
        verbose_name='Создано пользователем',
    )
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responded_token_invitations',
        verbose_name='Ответивший пользователь',
        null=True,
        blank=True,
    )
    responded_at = models.DateTimeField(
        'Дата ответа',
        null=True,
        blank=True,
    )
    expires_at = models.DateTimeField(
        'Действует до',
    )

    @property
    def resend_available_at(self):
        """Возвращает время доступности повторной отправки."""
        if self.status == TokenInvitationStatus.ACCEPTED:
            return None

        if self.last_sent_at is None:
            return timezone.now()

        return self.last_sent_at + timedelta(
            seconds=settings.INVITATION_RESEND_COOLDOWN_SECONDS,
        )

    @property
    def can_resend(self) -> bool:
        """Возвращает возможность повторной отправки."""
        available_at = self.resend_available_at

        return available_at is not None and available_at <= timezone.now()

    class Meta:
        verbose_name = 'инвайт'
        verbose_name_plural = 'инвайты'
        ordering = ('-created_at',)

    def register_send(self) -> None:
        """Фиксирует отправку приглашения."""
        self.send_count += 1
        self.last_sent_at = timezone.now()
        self.save(
            update_fields=(
                'send_count',
                'last_sent_at',
                'updated_at',
            ),
        )

    def __str__(self):
        return f'{self.recipient_email} — {self.get_status_display()}'


class ArtistProfileClaimInvitation(models.Model):
    """Приглашение к управлению профилем артиста."""

    invitation = models.OneToOneField(
        TokenInvitation,
        on_delete=models.CASCADE,
        related_name='artist_profile_claim',
        verbose_name='Приглашение',
    )
    artist = models.ForeignKey(
        ArtistProfile,
        on_delete=models.PROTECT,
        related_name='claim_invitations',
        verbose_name='Профиль артиста',
    )

    class Meta:
        verbose_name = 'приглашение на управление профилем'
        verbose_name_plural = 'приглашения на управление профилем'

    def __str__(self):
        return f'{self.artist} → {self.invitation.recipient_email}'
