from django.conf import settings

from common.access.artists import can_manage_artist


def get_content_artist(obj):
    """Возвращает публичный профиль артиста."""
    artist = getattr(obj, 'artist', None)
    if artist is not None:
        return artist

    album = getattr(obj, 'album', None)
    if album is not None:
        return album.artist

    return None


def can_manage_store_object(user, obj) -> bool:
    """Право пользователя управлять объектом витрины."""
    artist = get_content_artist(obj)

    if artist is None:
        return False

    return can_manage_artist(user, artist)


def can_preview_catalog_drafts(user) -> bool:
    """Определяет доступ к черновикам каталога."""
    mode = settings.CATALOG_DRAFT_PREVIEW_MODE

    if mode == 'all':
        return True

    if mode == 'staff':
        return bool(
            user and user.is_authenticated and user.is_staff,
        )

    return False
