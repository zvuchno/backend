"""Миксин для реализации мягкого удаления контента."""

from rest_framework import status
from rest_framework.response import Response


class SoftDeleteMixin:
    """Миксин для ViewSet: мягкое удаление объекта через API."""

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()

        # Мягкое удаление родителя
        obj.is_active = False
        obj.save()

        # Мягкое удаление связанных вариантов
        product = getattr(obj, 'product', None)
        if hasattr(product, 'variants'):
            product.variants.update(is_active=False)

        return Response(status=status.HTTP_204_NO_CONTENT)
