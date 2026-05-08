from django.db.models import Q
from rest_framework.permissions import BasePermission

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


class IsSalesOwner(BasePermission):
    """Доступ к заказу только продавцу (артисту) товаров в этом заказе.

    На уровне object-level:
    - разрешает доступ, если хотя бы один товар (`OrderItem`) в заказе
      принадлежит текущему пользователю через связь с альбомом,
      треком или мерчем.
    """

    message = 'Вы не являетесь продавцом товаров в этом заказе.'

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user

        # Если префетч уже отработал во ViewSet, используем его
        if (
            hasattr(obj, '_prefetched_objects_cache')
            and 'items' in obj._prefetched_objects_cache
        ):
            return any(
                (
                    item.product_variant.product.album
                    and item.product_variant.product.album.owner == user
                )
                or (
                    item.product_variant.product.track
                    and item.product_variant.product.track.owner == user
                )
                or (
                    item.product_variant.product.merch
                    and item.product_variant.product.merch.owner == user
                )
                for item in obj.items.all()
            )

        # Fallback
        return obj.items.filter(
            Q(product_variant__product__album__owner=user)
            | Q(product_variant__product__track__owner=user)
            | Q(product_variant__product__merch__owner=user),
        ).exists()
