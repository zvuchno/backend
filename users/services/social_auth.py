"""Сервисы для аутентификации через соцсети."""

import secrets

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from users.constants import (
    SOCIAL_SIGNUP_NONCE_BYTES,
    SOCIAL_SIGNUP_TOKEN_MAX_AGE,
    SOCIAL_SIGNUP_TOKEN_SALT,
)
from users.models import ListenerProfile

User = get_user_model()


def issue_token_for_user(user) -> dict:
    """Выдать токены пользователю."""
    refresh_token = RefreshToken.for_user(user)
    token = refresh_token.access_token
    return {
        'access': str(token),
        'refresh': str(refresh_token),
    }


def generate_username(email: str) -> str:
    """Сгенерировать username из email."""
    username = email.split('@')[0]
    new_username = username
    counter = 1
    while User.objects.filter(username=new_username).exists():
        new_username = f'{username}_{counter}'
        counter += 1
    return new_username


def build_auth_response(user, is_new_user: bool) -> dict:
    """Формирует ответ успешной аутентификации."""
    tokens = issue_token_for_user(user)
    return {
        **tokens,
        'is_new_user': is_new_user,
    }


def create_temp_signup_token(*, provider: str, provider_uid: str) -> str:
    """Выпускает временный токен для завершения регистрации через соцсеть."""
    payload = {
        'provider': provider,
        'provider_uid': provider_uid,
        'nonce': secrets.token_hex(SOCIAL_SIGNUP_NONCE_BYTES),
    }
    return signing.dumps(payload, salt=SOCIAL_SIGNUP_TOKEN_SALT)


def parse_temp_signup_token(signup_token: str) -> dict:
    """Разбирает временный токен регистрации."""
    try:
        return signing.loads(
            signup_token,
            salt=SOCIAL_SIGNUP_TOKEN_SALT,
            max_age=SOCIAL_SIGNUP_TOKEN_MAX_AGE,
        )
    except signing.SignatureExpired as exc:
        raise serializers.ValidationError(
            {'signup_token': 'Срок действия токена истек.'},
        ) from exc
    except signing.BadSignature as exc:
        raise serializers.ValidationError(
            {'signup_token': 'Некорректный токен.'},
        ) from exc


def ensure_listener_profile(user) -> None:
    """Проверяет наличие или создает профиль слушателя."""
    ListenerProfile.objects.get_or_create(user=user)


def set_unusable_password(user) -> None:
    """Задаем неиспользуемый пароль."""
    user.set_unusable_password()
    user.save(update_fields=['password'])


def get_vk_identity(*, code: str, redirect_uri: str) -> dict:
    """Получает identity пользователя от VK.

    Здесь позже будет реальная интеграция через allauth/VK provider.
    На выходе должен быть единый словарь вида:
    {
        'provider': 'vk',
        'provider_uid': '12345',
        'email': 'user@example.com' | None,
        'email_verified': True | False,
    }
    """
    raise NotImplementedError('VK integration is not implemented yet.')


def find_user_by_social_account(*, provider: str, provider_uid: str):
    """Ищет пользователя по привязанному social account.

    Здесь позже будет поиск через allauth SocialAccount.
    """
    return


def link_social_account(*, user, provider: str, provider_uid: str) -> None:
    """Привязывает social account к локальному пользователю.

    Здесь позже будет создание/связывание через allauth SocialAccount.
    """
    return


@transaction.atomic
def create_account_from_social(*, email: str, is_email_verified: bool) -> User:
    """Создаем аккаунт пользователя."""
    user = User.objects.create(
        email=email,
        username=generate_username(email),
        is_email_verified=is_email_verified,
    )
    set_unusable_password(user)
    ensure_listener_profile(user)
    return user


def login_with_vk(*, code: str, redirect_uri: str) -> dict:
    """Обрабатывает вход через VK."""
    identity = get_vk_identity(code=code, redirect_uri=redirect_uri)

    provider = identity['provider']
    provider_uid = identity['provider_uid']
    email = identity.get('email')
    email_verified = identity.get('email_verified', False)

    user = find_user_by_social_account(
        provider=provider,
        provider_uid=provider_uid,
    )
    if user:
        return build_auth_response(user, is_new_user=False)

    if email:
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            link_social_account(
                user=existing_user,
                provider=provider,
                provider_uid=provider_uid,
            )
            ensure_listener_profile(existing_user)
            return build_auth_response(existing_user, is_new_user=False)

        user = create_account_from_social(
            email=email,
            is_email_verified=email_verified,
        )
        link_social_account(
            user=user,
            provider=provider,
            provider_uid=provider_uid,
        )
        return build_auth_response(user, is_new_user=True)

    signup_token = create_temp_signup_token(
        provider=provider,
        provider_uid=provider_uid,
    )
    return {
        'result': 'profile_completion_required',
        'missing_fields': ['email'],
        'signup_token': signup_token,
    }


def complete_social_signup(*, signup_token: str, email: str) -> dict:
    """Завершить регистрацию через соцсеть."""
    data = parse_temp_signup_token(signup_token)
    provider = data['provider']
    provider_uid = data['provider_uid']
    if User.objects.filter(email=email).exists():
        raise serializers.ValidationError(
            {
                'email': 'Пользователь с таким email уже существует.',
            },
        )

    user = create_account_from_social(email=email, is_email_verified=False)
    link_social_account(
        user=user,
        provider=provider,
        provider_uid=provider_uid,
    )
    return build_auth_response(user, is_new_user=True)
