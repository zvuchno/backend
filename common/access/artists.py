from django.db.models import Q

from users.models import ArtistProfile


def can_manage_artist(user, artist: ArtistProfile | None) -> bool:
    """Проверяет право пользователя управлять публичным профилем."""
    if not user or not user.is_authenticated or artist is None:
        return False

    return artist.user_id == user.id or (
        artist.label_id is not None and artist.label.user_id == user.id
    )


def managed_artist_q(user, prefix='artist') -> Q:
    """Строит условие доступа к управляемым профилям артистов."""
    prefix = f'{prefix}__' if prefix else ''

    return Q(**{f'{prefix}user': user}) | Q(**{f'{prefix}label__user': user})
