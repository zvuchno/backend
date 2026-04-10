"""Пермишены для приложения пользователей."""

from rest_framework.permissions import BasePermission


class ActiveProfilePermission(BasePermission):
    """Базовый пермишен наличия активного профиля."""

    profile_attr = None
    message = 'Недостаточно прав.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and self.profile_attr):
            return False

        profile = getattr(user, self.profile_attr, None)
        return bool(profile and profile.is_active)


class IsListener(ActiveProfilePermission):
    """Пермишен наличия активного профиля слушателя."""

    profile_attr = 'listener_profile'
    message = 'Требуется профиль слушателя.'


class IsArtist(ActiveProfilePermission):
    """Пермишен наличия активного профиля артиста."""

    profile_attr = 'artist_profile'
    message = 'Требуется профиль артиста.'


class IsNotArtist(BasePermission):
    """Пермишен для аутентифицированного пользователя без профиля артиста."""

    message = 'Профиль артиста уже существует.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated) and not hasattr(
            user,
            'artist_profile',
        )


class IsStoreObjectOwner(BasePermission):
    """Пермишен владельца объекта витрины."""

    message = 'Вы не владелец.'

    def has_object_permission(self, request, view, obj):
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.owner == request.user,
        )


class IsUserObjectOwner(BasePermission):
    """Пермишен для владельца аккаунта, профиля или заказа."""

    message = 'Вы не владелец.'

    def has_object_permission(self, request, view, obj):
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.user == request.user,
        )
