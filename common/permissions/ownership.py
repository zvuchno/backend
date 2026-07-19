"""TODO: убрать не нужные."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from common.access import can_manage_store_object

from .base import (
    _IsOwnerByField,
    _IsOwnerByFieldOrReadOnly,
)


class IsStoreObjectManager(BasePermission):
    """Разрешает доступ пользователю, управляющему артистом объекта."""

    message = 'У вас нет прав на управление этим объектом.'

    def has_permission(self, request, view) -> bool:
        """Требует аутентифицированного пользователя."""
        return bool(
            request.user and request.user.is_authenticated,
        )

    def has_object_permission(self, request, view, obj) -> bool:
        """Проверяет право управления артистом объекта."""
        return can_manage_store_object(
            request.user,
            obj,
        )


class IsStoreObjectManagerOrReadOnly(BasePermission):
    """Разрешает чтение всем, изменение управляющему артистом."""

    message = 'У вас нет прав на изменение этого объекта.'

    def has_permission(self, request, view) -> bool:
        """Разрешает чтение всем, запись — аутентифицированным."""
        if request.method in SAFE_METHODS:
            return True

        return bool(
            request.user and request.user.is_authenticated,
        )

    def has_object_permission(self, request, view, obj) -> bool:
        """Разрешает чтение всем, изменение — управляющему."""
        if request.method in SAFE_METHODS:
            return True

        return can_manage_store_object(
            request.user,
            obj,
        )


class IsStoreObjectOwner(_IsOwnerByField):
    """Доступ к объекту витрины только его владельцу.

    Используется для object-level проверки моделей витрины,
    в которых владелец хранится в поле `owner`.

    Ограничивает доступ для любых методов, включая чтение.
    """

    owner_field_name = 'owner'


class IsUserObjectOwner(_IsOwnerByField):
    """Доступ к объекту только пользователю, связанному через поле `user`.

    Используется для object-level проверки моделей, где владелец
    или связанный пользователь хранится в поле `user`.

    Ограничивает доступ для любых методов, включая чтение.
    """

    owner_field_name = 'user'


class IsUserObjectOwnerOrReadOnly(_IsOwnerByFieldOrReadOnly):
    """Чтение объекта всем, изменение только пользователю из поля `user`.

    Используется для object-level проверки моделей, где связь
    с владельцем хранится в поле `user`.

    Безопасные методы доступны всем.
    Небезопасные методы доступны только владельцу объекта.
    """

    owner_field_name = 'user'


class IsSalesOwner(BasePermission):
    """Доступ к заказу только продавцу (артисту) товаров в этом заказе.

    На уровне object-level:
    - разрешает доступ, если хотя бы один товар (`OrderItem`) в заказе
      принадлежит текущему пользователю через связь с альбомом,
      треком или мерчем.
    """

    message = 'У вас нет доступа к продажам товаров в этом заказе.'

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not user.is_authenticated:
            return False

        return any(
            can_manage_store_object(
                user,
                item.product_variant.product,
            )
            for item in obj.items.all()
        )
