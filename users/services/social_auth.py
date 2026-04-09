"""Сервисы для аутентификации через соцсети."""

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from users.constants import MAX_USER_CREATE_ATTEMPTS
from users.models import ListenerProfile

User = get_user_model()


def issue_tokens_for_user(user) -> dict:
    """Выдать токены пользователю."""
    refresh_token = RefreshToken.for_user(user)
    token = refresh_token.access_token
    return {
        'access': str(token),
        'refresh': str(refresh_token),
    }


def generate_username(email: str, attempt: int) -> str:
    """Сгенерировать username из email."""
    username = normalize_email(email).split('@')[0] or 'user'
    return username if attempt == 0 else f'{username}_{attempt}'


def ensure_listener_profile(user) -> None:
    """Проверяет наличие или создает профиль слушателя."""
    ListenerProfile.objects.get_or_create(user=user)


def set_unusable_password(user) -> None:
    """Задаем неиспользуемый пароль."""
    user.set_unusable_password()
    user.save(update_fields=['password'])


def find_user_by_social_account(
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


def create_account_from_social(
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


def login_with_social_data(
    *,
    provider: str,
    provider_uid: str,
    email: str,
    is_email_verified: bool,
) -> User:
    """Обрабатывает вход через соцсеть."""
    user = find_user_by_social_account(
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

    return create_account_from_social(
        email=email,
        is_email_verified=is_email_verified,
    )


def normalize_email(email: str) -> str:
    """Нормализация email."""
    return email.strip().lower()
