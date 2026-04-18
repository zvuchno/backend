"""Пермишены для приложения пользователей."""

from rest_framework.permissions import BasePermission


class _ActiveProfilePermission(BasePermission):
    """Внутренний базовый пермишен наличия активного профиля.

    Используется только внутри этого модуля как основа для
    role-based view-level пермишенов.

    Доступ разрешается, если:
    - пользователь аутентифицирован;
    - в классе задан атрибут `profile_attr`;
    - у пользователя существует связанный профиль;
    - профиль активен (`is_active=True`).
    """

    profile_attr = None
    message = 'Недостаточно прав.'

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated and self.profile_attr):
            return False

        profile = getattr(user, self.profile_attr, None)
        return profile and profile.is_active


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
