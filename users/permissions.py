"""Пермишены для приложения пользователей."""

from rest_framework.permissions import BasePermission


class IsListener(BasePermission):
    """Пермишен роли слушателя."""

    message = 'Требуется профиль слушателя.'

    def has_permission(self, request, view):
        user = request.user
        return (
            bool(user and user.is_authenticated)
            and hasattr(user, 'listener_profile')
            and user.listener_profile.is_active
        )


class IsArtist(BasePermission):
    """Пермишен роли артиста."""

    message = 'Требуется профиль артиста.'

    def has_permission(self, request, view):
        user = request.user
        return (
            bool(user and user.is_authenticated)
            and hasattr(user, 'artist_profile')
            and user.artist_profile.is_active
        )


class IsNotArtist(BasePermission):
    """Пермишен для аутентифицированного пользователя Не артиста."""

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
        return (
            request.user
            and request.user.is_authenticated
            and obj.owner == request.user
        )


class IsUserObjectOwner(BasePermission):
    """Пермишен для владельца аккаунта, профиля или заказа."""

    message = 'Вы не владелец.'

    def has_object_permission(self, request, view, obj):
        return (
            request.user
            and request.user.is_authenticated
            and obj.user == request.user
        )
