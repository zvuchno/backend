"""Модуль миксинов для сериализаторов.

Содержит переиспользуемые классы-поведения (mixins), которые можно подключать
к различным сериализаторам. Эти миксины инкапсулируют общие действия и логику,
не зависящие от конкретной модели.
"""

from .images import ProductImagesMixin
from .immutable_fields import ImmutableFieldsSerializerMixin
from .product_variant_url_mixin import ProductVariantURLMixin

__all__ = [
    'ImmutableFieldsSerializerMixin',
    'ProductImagesMixin',
    'ProductVariantURLMixin',
]
