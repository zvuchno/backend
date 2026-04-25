from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from users.constants import (
    MAX_USER_CREATE_ATTEMPTS,
    SOCIAL_AUTH_ERRORS,
    SOCIAL_AUTH_ERROR_BLOCKED_USER,
    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
    SOCIAL_AUTH_ERROR_MISSING_EMAIL,
    SOCIAL_AUTH_ERROR_USERNAME_GENERATION_FAILED,
)
from users.exceptions import SocialAuthException
from users.helpers import (
    ensure_listener_profile,
    generate_username,
    normalize_email,
    set_unusable_password,
)

User = get_user_model()


class SocialAuthService:
    """Обрабатывает пользователя для входа через соцсеть."""

    def resolve_user(
        self,
        *,
        provider: str,
        provider_uid: str,
        email: str,
        is_email_verified: bool,
    ) -> User:
        """Возвращает существующего или создает нового пользователя."""
        user = self.find_user_by_social_account(
            provider=provider,
            provider_uid=provider_uid,
        )
        if user:
            self.ensure_user_is_active(user)
            ensure_listener_profile(user)
            return user

        if not email:
            raise SocialAuthException(
                SOCIAL_AUTH_ERROR_MISSING_EMAIL,
                SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_MISSING_EMAIL],
            )

        email = normalize_email(email)

        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            self.ensure_user_is_active(existing_user)
            ensure_listener_profile(existing_user)
            if not existing_user.is_email_verified:
                raise SocialAuthException(
                    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
                    SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED],
                )
            return existing_user

        return self._create_account_from_social(
            email=email,
            is_email_verified=is_email_verified,
        )

    def find_user_by_social_account(
        self,
        *,
        provider: str,
        provider_uid: str,
    ) -> User | None:
        """Ищет пользователя по привязанному social account."""
        social_account = (
            SocialAccount.objects
            .select_related('user')
            .filter(provider=provider, uid=str(provider_uid))
            .first()
        )
        return social_account.user if social_account else None

    def _create_account_from_social(
        self,
        *,
        email: str,
        is_email_verified: bool,
    ) -> User:
        """Создает пользователя из соцсети с retry при конфликте username."""
        for attempt in range(MAX_USER_CREATE_ATTEMPTS):
            try:
                with transaction.atomic():
                    user = User.objects.create(
                        email=email,
                        username=generate_username(email, attempt),
                        is_email_verified=is_email_verified,
                    )
                    set_unusable_password(user)
                    ensure_listener_profile(user)
                    return user

            except IntegrityError:
                existing_user = User.objects.filter(email=email).first()
                if existing_user:
                    self.ensure_user_is_active(existing_user)
                    ensure_listener_profile(existing_user)
                    if not existing_user.is_email_verified:
                        raise SocialAuthException(
                            SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
                            SOCIAL_AUTH_ERRORS[
                                SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED
                            ],
                        )
                    return existing_user
                continue
        raise SocialAuthException(
            SOCIAL_AUTH_ERROR_USERNAME_GENERATION_FAILED,
            SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_USERNAME_GENERATION_FAILED],
        )

    def ensure_user_is_active(self, user) -> None:
        """Проверить, что пользователь не заблокирован."""
        if user is None:
            return
        if not user.is_active:
            raise SocialAuthException(
                SOCIAL_AUTH_ERROR_BLOCKED_USER,
                SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_BLOCKED_USER],
            )
