from django.db.models import Q

from users.models import ArtistProfile


def can_manage_artist(user, artist: ArtistProfile) -> bool:
    """Проверяет право пользователя управлять публичным профилем."""
    if not user or not user.is_authenticated:
        return False

    if artist.label_id is not None:
        return artist.label.user_id == user.id

    return artist.user_id == user.id


def managed_artist_q(user, prefix='artist') -> Q:
    """Строит условие объектов управляемых артистов."""
    return Q(**{f'{prefix}__user': user}) | Q(**{
        f'{prefix}__label__user': user,
    })
