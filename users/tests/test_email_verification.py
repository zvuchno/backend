"""Тесты подтверждения email по коду."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from users.constants import EMAIL_VERIFICATION_CODE_MAX_ATTEMPTS
from users.models import EmailVerificationCode
from users.services.email_verification import (
    create_email_verification_code,
    hash_email_verification_code,
)

pytestmark = pytest.mark.django_db


class TestEmailVerificationCode:
    """Тесты подтверждения email по коду."""

    def test_valid_code_verifies_email(
        self,
        auth_client,
        user,
        verify_email_code_url,
    ):
        """Корректный код подтверждает email пользователя."""
        user.is_email_verified = False
        user.save(update_fields=('is_email_verified',))

        code = create_email_verification_code(user)

        response = auth_client.post(
            verify_email_code_url,
            {'code': code},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()

        assert user.is_email_verified is True
        assert not EmailVerificationCode.objects.filter(user=user).exists()

    def test_invalid_code_does_not_verify_email(
        self,
        auth_client,
        user,
        verify_email_code_url,
    ):
        """Неверный код не подтверждает email."""
        user.is_email_verified = False
        user.save(update_fields=('is_email_verified',))

        create_email_verification_code(user)

        response = auth_client.post(
            verify_email_code_url,
            {'code': '000000'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        verification = EmailVerificationCode.objects.get(user=user)

        assert user.is_email_verified is False
        assert verification.attempts == 1

    def test_expired_code_is_rejected(
        self,
        auth_client,
        user,
        verify_email_code_url,
    ):
        """Просроченный код не подтверждает email."""
        user.is_email_verified = False
        user.save(update_fields=('is_email_verified',))

        code = '123456'
        EmailVerificationCode.objects.create(
            user=user,
            code_hash=hash_email_verification_code(code),
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = auth_client.post(
            verify_email_code_url,
            {'code': code},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        assert user.is_email_verified is False

    def test_code_is_blocked_after_max_attempts(
        self,
        auth_client,
        user,
        verify_email_code_url,
    ):
        """После превышения числа попыток код больше не принимается."""
        user.is_email_verified = False
        user.save(update_fields=('is_email_verified',))

        code = '123456'
        EmailVerificationCode.objects.create(
            user=user,
            code_hash=hash_email_verification_code(code),
            expires_at=timezone.now() + timedelta(minutes=15),
            attempts=EMAIL_VERIFICATION_CODE_MAX_ATTEMPTS,
        )

        response = auth_client.post(
            verify_email_code_url,
            {'code': code},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        assert user.is_email_verified is False

    def test_code_is_required_to_have_valid_format(
        self,
        auth_client,
        verify_email_code_url,
    ):
        """Код должен состоять из необходимого количества цифр."""
        response = auth_client.post(
            verify_email_code_url,
            {'code': '12345'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'code' in response.data

    def test_requires_authentication(
        self,
        api_client,
        verify_email_code_url,
    ):
        """Подтверждение кодом требует авторизации."""
        response = api_client.post(
            verify_email_code_url,
            {'code': '123456'},
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_resend_replaces_verification_code(
        self,
        auth_client,
        user,
        resend_email_verification_url,
    ):
        """Повторная отправка заменяет активный код подтверждения."""
        user.is_email_verified = False
        user.save(update_fields=('is_email_verified',))

        create_email_verification_code(user)

        verification = EmailVerificationCode.objects.get(user=user)
        verification.attempts = 3
        verification.save(update_fields=('attempts',))

        old_hash = verification.code_hash
        old_expires_at = verification.expires_at

        response = auth_client.post(
            resend_email_verification_url,
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        verification.refresh_from_db()

        assert verification.code_hash != old_hash
        assert verification.expires_at > old_expires_at
        assert verification.attempts == 0
