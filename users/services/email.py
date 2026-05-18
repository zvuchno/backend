from common.services.email import send_template_email


def send_email_verification_mail(to_email, verification_url: str) -> None:
    """Отправляет письмо подтверждения email."""
    send_template_email(
        subject='Подтверждение email на платформе Звучно',
        to_email=to_email,
        template_name='email_verification',
        context={
            'verification_url': verification_url,
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
