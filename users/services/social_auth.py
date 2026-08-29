from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from common.utils import normalize_email

from users.consents_policy import ConsentScenario
from users.constants import (
    MAX_USER_CREATE_ATTEMPTS,
    SOCIAL_AUTH_ERRORS,
    SOCIAL_AUTH_ERROR_BLOCKED_USER,
    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
    SOCIAL_AUTH_ERROR_MISSING_EMAIL,
    SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED,
    SOCIAL_AUTH_ERROR_USERNAME_GENERATION_FAILED,
)
from users.exceptions import SocialAuthException
from users.helpers import (
    ensure_listener_profile,
    generate_username,
    set_unusable_password,
)
from users.services import ConsentService

User = get_user_model()


class SocialAuthService:
    """Обрабатывает пользователя для входа через соцсеть."""

    def find_user_by_email(self, email: str) -> User | None:
        """Ищет пользователя по email."""
        if not email:
            return None

        return User.objects.filter(
            email=normalize_email(email),
        ).first()

    def mark_email_verified_from_social_provider(
        self,
        *,
        user: User | None,
        email: str,
        is_email_verified: bool,
    ) -> None:
        """Подтверждает email пользователя доверенным провайдером."""
        if not user or not email or not is_email_verified:
            return

        if normalize_email(user.email) != normalize_email(email):
            return

        if user.is_email_verified:
            return

        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])

    def resolve_user(
        self,
        *,
        provider: str,
        provider_uid: str,
        email: str,
        is_email_verified: bool,
        create_account: bool = False,
        accepted_consents=(),
        ip_address: str | None = None,
        user_agent: str = '',
    ) -> User:
        """Возвращает существующего или создает нового пользователя."""
        user = self.find_user_by_social_account(
            provider=provider,
            provider_uid=provider_uid,
        )
        if user:
            self.ensure_user_is_active(user)
            ensure_listener_profile(user)
            self.mark_email_verified_from_social_provider(
                user=user,
                email=email,
                is_email_verified=is_email_verified,
            )
            return user

        if not email:
            raise SocialAuthException(
                SOCIAL_AUTH_ERROR_MISSING_EMAIL,
                SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_MISSING_EMAIL],
            )

        email = normalize_email(email)

        existing_user = self.find_user_by_email(email)
        if existing_user:
            self.ensure_user_is_active(existing_user)
            ensure_listener_profile(existing_user)
            self.mark_email_verified_from_social_provider(
                user=existing_user,
                email=email,
                is_email_verified=is_email_verified,
            )

            if not existing_user.is_email_verified:
                raise SocialAuthException(
                    SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED,
                    SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_EMAIL_NOT_CONFIRMED],
                )

            return existing_user

        if not create_account:
            raise SocialAuthException(
                SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED,
                SOCIAL_AUTH_ERRORS[SOCIAL_AUTH_ERROR_REGISTRATION_REQUIRED],
            )

        accepted_consents = set(accepted_consents)

        ConsentService.validate(
            scenario=ConsentScenario.LISTENER_REGISTRATION,
            accepted_types=accepted_consents,
        )

        user, created = self._create_account_from_social(
            email=email,
            is_email_verified=is_email_verified,
        )

        if created:
            ConsentService.accept(
                scenario=ConsentScenario.LISTENER_REGISTRATION,
                accepted_types=accepted_consents,
                user=user,
                email=user.email,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return user

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
    ) -> tuple[User, bool]:
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
                    return user, True

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
                    return existing_user, False
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
