from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
)


class _ActiveProfilePermission(BasePermission):
    """Базовый пермишен наличия активного профиля.

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
        return bool(profile and profile.is_active)


class _IsOwnerByField(BasePermission):
    """Базовый пермишен проверки доступа по полю владельца.

    На уровне view-level:
    - требует аутентифицированного пользователя;
    - требует, чтобы в классе было задано имя поля `owner_field_name`.

    На уровне object-level:
    - разрешает доступ только если значение поля `owner_field_name`
      у объекта совпадает с `request.user`.
    """

    owner_field_name = None
    message = 'Вы не владелец объекта.'

    def has_permission(self, request, view) -> bool:
        """Для любых методов требует аутентифицированного пользователя."""
        user = request.user
        return bool(
            user and user.is_authenticated and self.owner_field_name,
        )

    def has_object_permission(self, request, view, obj) -> bool:
        """Проверяет, что пользователь совпадает со значением owner-поля."""
        user = request.user
        if not (user and user.is_authenticated and self.owner_field_name):
            return False
        return getattr(obj, self.owner_field_name, None) == user


class _IsOwnerByFieldOrReadOnly(_IsOwnerByField):
    """Базовый пермишен: чтение всем, изменение владельцу.

    На уровне view-level:
    - безопасные методы доступны всем;
    - небезопасные методы доступны только аутентифицированному пользователю.

    На уровне object-level:
    - безопасные методы доступны всем;
    - небезопасные методы доступны только владельцу объекта.
    """

    def has_permission(self, request, view) -> bool:
        """Разрешает чтение всем, изменение — только аутентифицированным."""
        if request.method in SAFE_METHODS:
            return True
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj) -> bool:
        """Разрешает чтение всем, изменение — только владельцу."""
        if request.method in SAFE_METHODS:
            return True
        return super().has_object_permission(request, view, obj)
