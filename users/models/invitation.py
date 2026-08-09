from django.conf import settings
from django.db import models

from common.models.abstract import TimestampModel

from users.models import ArtistProfile


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

    class Meta:
        verbose_name = 'инвайт'
        verbose_name_plural = 'инвайты'
        ordering = ('-created_at',)

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
