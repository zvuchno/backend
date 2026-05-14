"""Сервис подтверждения email.

Пока без отправки письма.
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import (
    urlsafe_base64_encode,
)

from users.services import send_email_verification_mail


def generate_email_verification_data(user) -> dict:
    """Генерирует данные для подтверждения email пользователя."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return {
        'uid': uid,
        'token': token,
    }


def build_email_verification_url(user, frontend_base_url: str) -> str:
    """Строит ссылку подтверждения email для фронтенда."""
    data = generate_email_verification_data(user)
    return f'{frontend_base_url}?uid={data["uid"]}&token={data["token"]}'


def verify_email_token(user, token: str) -> bool:
    """Проверяет токен подтверждения email."""
    return default_token_generator.check_token(user, token)


def request_email_verification(user) -> str:
    """Формирует ссылку подтверждения email и отправляет письмо."""
    verification_url = build_email_verification_url(
        user=user,
        frontend_base_url=settings.FRONTEND_VERIFY_EMAIL_URL,
    )
    send_email_verification_mail(
        to_email=user.email,
        verification_url=verification_url,
    )
    return verification_url
