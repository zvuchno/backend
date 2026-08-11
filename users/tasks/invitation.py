from celery import shared_task
from django.utils import timezone

from users.models import TokenInvitation, TokenInvitationStatus


@shared_task
def expire_token_invitations() -> int:
    """Помечает просроченные приглашения истёкшими."""
    return TokenInvitation.objects.filter(
        status=TokenInvitationStatus.PENDING,
        expires_at__lte=timezone.now(),
    ).update(
        status=TokenInvitationStatus.EXPIRED,
        updated_at=timezone.now(),
    )
