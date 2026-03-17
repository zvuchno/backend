"""Сервис подтверждения email.

Пока без отправки письма, с выводом в терминал.
"""

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import (
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)


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


def get_user_from_uid(uid, user_model):
    """Возвращает пользователя по uid или None."""
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        return user_model.objects.get(pk=user_id)
    except Exception:
        return None


def verify_email_token(user, token: str) -> bool:
    """Проверяет токен подтверждения email."""
    return default_token_generator.check_token(user, token)
