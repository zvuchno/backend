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
    """Строит условие доступа пользователя к профилю артиста.

    Профиль считается доступным, если пользователь:

    - напрямую связан с ним через ArtistProfile.user;
    - является владельцем лейбла, указанного в
      ArtistProfile.label, то есть находится через
      ArtistProfile.label.user.

    prefix задаёт ORM-путь от модели текущего queryset до
    ArtistProfile. По умолчанию предполагается, что текущая модель
    связана с профилем полем artist, тогда:

    artist__user=user или artist__label__user=user.

    При фильтрации самого ArtistProfile нужно передать пустой
    префикс, чтобы получить:

    user=user или label__user=user.
    """
    prefix = f'{prefix}__' if prefix else ''

    return Q(**{f'{prefix}user': user}) | Q(**{f'{prefix}label__user': user})
