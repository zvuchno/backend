"""Сервис подтверждения email."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.encoding import force_bytes
from django.utils.http import (
    urlsafe_base64_encode,
)

from common.utils.urls import build_frontend_url

from users.constants import (
    EMAIL_VERIFICATION_CODE_LENGTH,
    EMAIL_VERIFICATION_CODE_TTL_MINUTES,
)
from users.models import EmailVerificationCode
from users.services import send_email_verification_mail


def generate_email_verification_data(user) -> dict:
    """Генерирует данные для подтверждения email пользователя."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return {
        'uid': uid,
        'token': token,
    }


def build_email_verification_url(user) -> str:
    """Строит ссылку подтверждения email для фронтенда."""
    return build_frontend_url(
        settings.FRONTEND_VERIFY_EMAIL_PATH,
        generate_email_verification_data(user),
    )


def verify_email_token(user, token: str) -> bool:
    """Проверяет токен подтверждения email."""
    return default_token_generator.check_token(user, token)


def request_email_verification(user) -> dict:
    """Формирует данные подтверждения email и отправляет письмо."""
    verification_url = build_email_verification_url(user)
    verification_code = create_email_verification_code(user)

    send_email_verification_mail(
        to_email=user.email,
        verification_url=verification_url,
        verification_code=verification_code,
    )

    return {
        'verification_url': verification_url,
        'verification_code': verification_code,
    }


def create_email_verification_code(user) -> str:
    """Создает новый код подтверждения email пользователя."""
    code = generate_email_verification_code()

    EmailVerificationCode.objects.update_or_create(
        user=user,
        defaults={
            'code_hash': hash_email_verification_code(code),
            'expires_at': (
                timezone.now()
                + timedelta(minutes=EMAIL_VERIFICATION_CODE_TTL_MINUTES)
            ),
            'attempts': 0,
        },
    )

    return code


def generate_email_verification_code() -> str:
    """Генерирует цифровой код подтверждения email."""
    return ''.join(
        str(secrets.randbelow(10))
        for _ in range(EMAIL_VERIFICATION_CODE_LENGTH)
    )


def hash_email_verification_code(code: str) -> str:
    """Возвращает защищенный хэш кода подтверждения email."""
    return salted_hmac(
        key_salt='users.email_verification_code',
        value=code,
    ).hexdigest()
