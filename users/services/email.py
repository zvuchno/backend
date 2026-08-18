from common.services.email import send_template_email

from users.constants import EMAIL_VERIFICATION_CODE_TTL_MINUTES


def send_email_verification_mail(
    to_email: str,
    verification_url: str,
    verification_code: str,
) -> None:
    """Отправляет письмо подтверждения email."""
    send_template_email(
        subject='Подтверждение email на платформе Звучно',
        to_email=to_email,
        template_name='email_verification',
        context={
            'verification_url': verification_url,
            'verification_code': verification_code,
            'verification_code_ttl_minutes': (
                EMAIL_VERIFICATION_CODE_TTL_MINUTES
            ),
        },
    )


def send_password_reset_email(to_email, reset_url: str) -> None:
    """Отправляет письмо восстановления пароля."""
    send_template_email(
        subject='Восстановление пароля на платформе Звучно',
        to_email=to_email,
        template_name='password_reset',
        context={
            'reset_url': reset_url,
        },
    )


def send_artist_profile_claim_invitation_mail(
    *,
    to_email: str,
    artist_name: str,
    label_name: str,
    invitation_url: str,
) -> None:
    """Отправляет приглашение на управление профилем артиста."""
    send_template_email(
        subject='Приглашение на платформу Звучно',
        to_email=to_email,
        template_name='artist_profile_claim_invitation',
        context={
            'artist_name': artist_name,
            'label_name': label_name,
            'invitation_url': invitation_url,
        },
    )


def send_artist_profile_claim_accepted_mail(
    *,
    to_email: str,
    artist_name: str,
    recipient_email: str,
) -> None:
    """Уведомляет о принятии приглашения."""
    send_template_email(
        subject='Приглашение принято',
        to_email=to_email,
        template_name='artist_profile_claim_accepted',
        context={
            'artist_name': artist_name,
            'recipient_email': recipient_email,
        },
    )


def send_artist_profile_claim_rejected_mail(
    *,
    to_email: str,
    artist_name: str,
    recipient_email: str,
) -> None:
    """Уведомляет об отклонении приглашения."""
    send_template_email(
        subject='Приглашение отклонено',
        to_email=to_email,
        template_name='artist_profile_claim_rejected',
        context={
            'artist_name': artist_name,
            'recipient_email': recipient_email,
        },
    )
