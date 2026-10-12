"""Хелперы для работы с аутентификацией."""

import logging

from common.utils.normalization import normalize_email

from store.services.cart_service import CartService

logger = logging.getLogger(__name__)

_SESSION_KEY_UNSET = object()


def generate_username(email: str, attempt: int) -> str:
    """Сгенерировать username из email."""
    username = normalize_email(email).split('@')[0] or 'user'
    return username if attempt == 0 else f'{username}_{attempt}'


def set_unusable_password(user) -> None:
    """Задаем неиспользуемый пароль."""
    user.set_unusable_password()
    user.save(update_fields=['password'])


def run_actions_after_authentication(
    user,
    request,
    *,
    session_key=_SESSION_KEY_UNSET,
) -> None:
    """Выполнить действия после аутентификации."""
    # Аутентификация пользователя с объединением корзин.
    # После успешной валидации учетных данных выполняется merge
    # гостевой корзины (session_key) с корзиной пользователя.
    try:
        if session_key is _SESSION_KEY_UNSET:
            session_key = request.session.session_key

        CartService.merge_carts(user, session_key)
    except Exception:
        logger.exception(
            'Не удалось объединить корзину для пользователя id=%s',
            user.id,
        )
