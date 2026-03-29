"""Сервис восстановления пароля.

Пока без отправки письма.
"""

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


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
