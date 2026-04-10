"""Пермишены для витрины."""

from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
)


class IsOwnerByField(BasePermission):
    """Пермишен владельца по полю объекта."""

    owner_field_name = None
    message = 'Вы не владелец объекта.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated and self.owner_field_name):
            return False
        return bool(
            getattr(obj, self.owner_field_name, None) == user,
        )


class IsOwnerByFieldOrReadOnly(IsOwnerByField):
    """Разрешено чтение для всех, изменение только владельцу."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return super().has_object_permission(request, view, obj)


class IsStoreObjectOwner(IsOwnerByField):
    """Владелец объекта витрины."""

    owner_field_name = 'owner'


class IsStoreObjectOwnerOrReadOnly(IsOwnerByFieldOrReadOnly):
    """Чтение всем, изменение — только владельцу объекта."""

    owner_field_name = 'owner'


class IsUserObjectOwner(IsOwnerByField):
    """Владелец пользовательского объекта витрины."""

    owner_field_name = 'user'


class IsUserObjectOwnerOrReadOnly(IsOwnerByFieldOrReadOnly):
    """Чтение всем, изменение — только владельцу пользовательского объекта."""

    owner_field_name = 'user'
