"""Celery-задачи отправки email."""

from celery import shared_task

from common.services.email import (
    EMAIL_SEND_EXCEPTIONS,
    _send_template_email,
)


@shared_task(
    autoretry_for=EMAIL_SEND_EXCEPTIONS,
    retry_backoff=30,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_template_email_task(
    *,
    subject: str,
    to_email: str,
    template_name: str,
    context: dict,
) -> None:
    """Отправляет текстовое и HTML-письмо."""
    _send_template_email(
        subject=subject,
        to_email=to_email,
        template_name=template_name,
        context=context,
    )
