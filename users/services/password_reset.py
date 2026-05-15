"""Сервис восстановления пароля.

Пока без отправки письма.
"""

import logging

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.services.email import EMAIL_SEND_EXCEPTIONS

from config import settings
from users.services import send_password_reset_email

logger = logging.getLogger(__name__)


def generate_password_reset_data(user) -> dict:
    """Создает данные для восстановления пароля."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return {
        'uid': uid,
        'token': token,
    }


def build_password_reset_url(user, front_url: str) -> str:
    """Генерирует ссылку для восстановления пароля."""
    data = generate_password_reset_data(user)
    return f'{front_url}?uid={data["uid"]}&token={data["token"]}'


def verify_password_reset_token(user, token: str) -> bool:
    """Проверяет токен восстановления пароля."""
    return default_token_generator.check_token(user, token)


def request_password_reset(user) -> str:
    """Формирует ссылку восстановления пароля и отправляет письмо."""
    reset_url = build_password_reset_url(
        user=user,
        front_url=settings.FRONTEND_RESET_PASSWORD_URL,
    )
    try:
        send_password_reset_email(
            to_email=user.email,
            reset_url=reset_url,
        )
    except EMAIL_SEND_EXCEPTIONS as exc:
        logger.warning(
            'Password reset email send '
            'failed | user_id=%s | email=%s | error=%s',
            user.id,
            user.email,
            exc,
        )
    return reset_url
