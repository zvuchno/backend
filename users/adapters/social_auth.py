"""Адаптеры для интеграции входа с соцсетями."""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.db import transaction

from users.services import ensure_listener_profile, login_with_social_data


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

        user = login_with_social_data(
            provider=provider,
            provider_uid=uid,
            email=email,
            is_email_verified=is_email_verified,
        )

        sociallogin.user = user
        return user
