"""Хелперы для профилей."""

from users.models import ListenerProfile


def ensure_listener_profile(user) -> None:
    """Возвращает профиль слушателя, создавая его при отсутствии."""
    ListenerProfile.objects.get_or_create(user=user)
