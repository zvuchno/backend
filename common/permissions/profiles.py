from rest_framework.permissions import BasePermission

from .base import _ActiveProfilePermission


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
    message = 'Требуется профиль артиста.'


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
