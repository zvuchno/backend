"""Пермишены для витрины."""

from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
)


class _IsOwnerByField(BasePermission):
    """Внутренний базовый пермишен проверки владельца по имени поля.

    Используется только внутри этого модуля как основа для
    конкретных object-level пермишенов.

    Доступ разрешается, если:
    - пользователь аутентифицирован;
    - в классе задано имя поля `owner_field_name`;
    - значение этого поля у объекта совпадает с `request.user`.
    """

    owner_field_name = None
    message = 'Вы не владелец объекта.'

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not (user and user.is_authenticated and self.owner_field_name):
            return False
        return getattr(obj, self.owner_field_name, None) == user


class _IsOwnerByFieldOrReadOnly(_IsOwnerByField):
    """Внутренний базовый пермишен: чтение всем, изменение владельцу.

    Используется только внутри этого модуля как основа для
    конкретных object-level пермишенов.

    Для безопасных методов (`GET`, `HEAD`, `OPTIONS`) доступ
    разрешается без проверки владельца.
    Для небезопасных методов (`POST`, `PATCH`, `PUT`, `DELETE`)
    доступ разрешается только владельцу объекта.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return super().has_object_permission(request, view, obj)


class IsStoreObjectOwner(_IsOwnerByField):
    """Доступ к объекту витрины только его владельцу.

    Используется для object-level проверки моделей витрины,
    в которых владелец хранится в поле `owner`.

    Ограничивает доступ для любых методов, включая чтение.
    """

    owner_field_name = 'owner'


class IsStoreObjectOwnerOrReadOnly(_IsOwnerByFieldOrReadOnly):
    """Чтение объекта витрины всем, изменение только владельцу.

    Используется для object-level проверки моделей витрины,
    в которых владелец хранится в поле `owner`.

    Безопасные методы доступны всем.
    Небезопасные методы доступны только владельцу объекта.
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
