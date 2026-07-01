"""Хелперы для работы с аутентификацией."""

import logging

from rest_framework_simplejwt.tokens import RefreshToken

from common.utils.normalization import normalize_email

from store.services.cart_service import CartService

logger = logging.getLogger(__name__)


def issue_tokens_for_user(user) -> dict:
    """Выдать токены пользователю."""
    refresh_token = RefreshToken.for_user(user)
    access_token = refresh_token.access_token
    return {
        'access': str(access_token),
        'refresh': str(refresh_token),
    }


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
    # Аутентификация пользователя с объединением корзин.
    # После успешной валидации учетных данных выполняется merge
    # гостевой корзины (session_key) с корзиной пользователя.
    logger.warning('=== RUN ACTIONS AFTER AUTH DEBUG ===')
    logger.warning(f'user: {user}, user.id: {user.id}')
    logger.warning(f'request.COOKIES in serializer: {request.COOKIES}')
    logger.warning(
        f'session.session_key in serializer: {request.session.session_key}',
    )
    try:
        CartService.merge_carts(user, request)
    except Exception:
        logger.exception(
            'Не удалось объединить корзину для пользователя id=%s',
            user.id,
        )
