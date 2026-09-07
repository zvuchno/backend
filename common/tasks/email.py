"""Celery-задачи отправки email."""

import smtplib

from celery import shared_task

from common.services.email import _send_template_email


@shared_task(
    bind=True,
    autoretry_for=(
        TimeoutError,
        OSError,
        smtplib.SMTPServerDisconnected,
    ),
    retry_backoff=30,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_template_email_task(
    self,
    *,
    subject: str,
    to_email: str,
    template_name: str,
    context: dict,
) -> None:
    """Отправляет текстовое и HTML-письмо."""
    try:
        _send_template_email(
            subject=subject,
            to_email=to_email,
            template_name=template_name,
            context=context,
        )
    except smtplib.SMTPResponseException as exc:
        if 400 <= exc.smtp_code < 500:
            countdown = min(
                30 * 2**self.request.retries,
                300,
            )
            raise self.retry(
                exc=exc,
                countdown=countdown,
            )

        raise
