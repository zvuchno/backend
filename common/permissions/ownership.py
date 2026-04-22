from .base import (
    _IsOwnerByField,
    _IsOwnerByFieldOrReadOnly,
)


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
