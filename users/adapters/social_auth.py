"""Адаптеры для интеграции входа с соцсетями."""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import serializers

from users.constants import MAX_USER_CREATE_ATTEMPTS
from users.helpers import (
    ensure_listener_profile,
    generate_username,
    normalize_email,
    set_unusable_password,
)

User = get_user_model()


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Адаптер регистрации и аутентификации через соцсеть."""

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        """Переопределим создание учетки."""
        provider = sociallogin.account.provider
        uid = sociallogin.account.uid
        email = sociallogin.user.email
        is_email_verified = self.is_email_verified(provider, email)

        # TODO в зависимости от фронта убедится есть ли request.user
        # TODO Скорее всего надо будет делать ручку
        if request and request.user.is_authenticated:
            user = request.user
            sociallogin.user = user
            ensure_listener_profile(user)
            return user

        user = self._login_with_social_data(
            provider=provider,
            provider_uid=uid,
            email=email,
            is_email_verified=is_email_verified,
        )

        sociallogin.user = user
        return user

    @staticmethod
    def _find_user_by_social_account(
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
                    return existing_user
                continue
        raise serializers.ValidationError(
            {'username': 'Не удалось подобрать уникальный username.'},
        )

    def _login_with_social_data(
        self,
        *,
        provider: str,
        provider_uid: str,
        email: str,
        is_email_verified: bool,
    ) -> User:
        """Обрабатывает вход через соцсеть."""
        user = self._find_user_by_social_account(
            provider=provider,
            provider_uid=provider_uid,
        )
        if user:
            ensure_listener_profile(user)
            return user

        if not email:
            raise serializers.ValidationError({'email': 'Отсутствует email.'})
        email = normalize_email(email)

        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            ensure_listener_profile(existing_user)
            if is_email_verified and not existing_user.is_email_verified:
                existing_user.is_email_verified = True
                existing_user.save(update_fields=['is_email_verified'])
            return existing_user

        return self._create_account_from_social(
            email=email,
            is_email_verified=is_email_verified,
        )
