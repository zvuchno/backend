"""Хелперы для работы с аутентификацией."""

from rest_framework_simplejwt.tokens import RefreshToken


def issue_tokens_for_user(user) -> dict:
    """Выдать токены пользователю."""
    refresh_token = RefreshToken.for_user(user)
    access_token = refresh_token.access_token
    return {
        'access': str(access_token),
        'refresh': str(refresh_token),
    }


def normalize_email(email: str) -> str:
    """Нормализация email."""
    return email.strip().lower()


def generate_username(email: str, attempt: int) -> str:
    """Сгенерировать username из email."""
    username = normalize_email(email).split('@')[0] or 'user'
    return username if attempt == 0 else f'{username}_{attempt}'


def set_unusable_password(user) -> None:
    """Задаем неиспользуемый пароль."""
    user.set_unusable_password()
    user.save(update_fields=['password'])


def run_actions_after_authentication(user, request) -> None:
    """Выполнить действия после аутентификации."""
