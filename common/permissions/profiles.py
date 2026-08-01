from rest_framework.permissions import BasePermission

from .base import _ActiveProfilePermission
from users.models.artist_profile import ArtistProfileType


class IsListener(_ActiveProfilePermission):
    """Доступ только пользователю с активным профилем слушателя.

    Проверяет наличие у текущего пользователя связанного
    `listener_profile` и его активный статус.
    """

    profile_attr = 'listener_profile'
    message = 'Требуется профиль слушателя.'


class IsArtist(_ActiveProfilePermission):
    """Доступ только пользователю с активным профилем артиста.

    Проверяет наличие у текущего пользователя связанного
    `artist_profile` и его активный статус.
    """

    profile_attr = 'artist_profile'
    allowed_profile_types = (ArtistProfileType.ARTIST,)
    message = 'Требуется профиль артиста.'


class IsLabel(_ActiveProfilePermission):
    """Доступ только пользователю с активным профилем лейбла."""

    profile_attr = 'artist_profile'
    allowed_profile_types = (ArtistProfileType.LABEL,)
    message = 'Требуется профиль лейбла.'


class IsNotLabel(BasePermission):
    """Разрешает доступ пользователям без профиля лейбла."""

    message = 'Операция недоступна для профиля лейбла.'

    def has_permission(self, request, view):
        """Проверяет, что пользователь не является лейблом."""
        profile = getattr(request.user, 'artist_profile', None)

        return (
            profile is None or profile.profile_type != ArtistProfileType.LABEL
        )


class IsArtistOrLabel(_ActiveProfilePermission):
    """Доступ только пользователю с активным профилем артиста или лейбла.

    Проверяет наличие у текущего пользователя связанного
    `artist_profile` и его активный статус.
    """

    profile_attr = 'artist_profile'
    allowed_profile_types = (
        ArtistProfileType.ARTIST,
        ArtistProfileType.LABEL,
    )
    message = 'Требуется профиль артиста или лейбла.'


class IsNotArtist(BasePermission):
    """Доступ только пользователю без существующего профиля артиста.

    Используется в сценариях, где профиль артиста должен
    быть создан впервые, например для ручки `become_artist`.

    Требует аутентифицированного пользователя и отсутствия
    связанного `artist_profile`.
    """

    message = 'Профиль артиста уже существует.'

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return not hasattr(
            user,
            'artist_profile',
        )


class CanCreateArtistContent(BasePermission):
    """Разрешает создание контента артисту, лейблу или менеджеру."""

    message = 'У вас нет прав на создание контента артиста.'

    def has_permission(self, request, view):
        """Проверяет наличие профиля артиста или лейбла."""
        if not request.user or not request.user.is_authenticated:
            return False

        profile = getattr(request.user, 'artist_profile', None)

        return bool(
            profile
            and profile.profile_type
            in (
                ArtistProfileType.ARTIST,
                ArtistProfileType.LABEL,
            ),
        )
