"""Вспомогательные функции сервисов пользователей."""

from django.utils.http import urlsafe_base64_decode


def get_user_from_uid(uid, user_model):
    """Возвращает пользователя по uid или None."""
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        return user_model.objects.get(pk=user_id)
    except Exception:
        return None


def set_user_password(user, raw_password):
    """Устанавливает пользователю новый пароль."""
    user.set_password(raw_password)
    user.save(update_fields=['password'])
