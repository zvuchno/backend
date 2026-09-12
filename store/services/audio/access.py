from django.conf import settings


def playback_mode_allows_full_access(user) -> bool:
    """Проверяет глобальный доступ к полной версии трека."""
    mode = settings.PLAYER_STREAM_MODE

    if mode == 'public':
        return True

    if mode == 'authenticated':
        return bool(user and user.is_authenticated)

    return False
