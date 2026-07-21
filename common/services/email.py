import smtplib
import socket

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

EMAIL_SEND_EXCEPTIONS = (
    smtplib.SMTPException,
    TimeoutError,
    socket.timeout,
    OSError,
)


def send_template_email(
    *,
    subject: str,
    to_email: str,
    template_name: str,
    context: dict,
) -> None:
    """Ставит текстовое и HTML-письмо в очередь на отправку."""
    from common.tasks.email import send_template_email_task

    send_template_email_task.delay(
        subject=subject,
        to_email=to_email,
        template_name=template_name,
        context=context,
    )


def _send_template_email(
    *,
    subject: str,
    to_email: str,
    template_name: str,
    context: dict,
) -> None:
    """Непосредственно отправляет текстовое и HTML-письмо."""
    text_body = render_to_string(f'emails/{template_name}.txt', context)
    html_body = render_to_string(f'emails/{template_name}.html', context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)
