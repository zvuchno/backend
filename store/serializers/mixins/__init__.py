"""Модуль миксинов для сериализаторов.

Содержит переиспользуемые классы-поведения (mixins), которые можно подключать
к различным сериализаторам. Эти миксины инкапсулируют общие действия и логику,
не зависящие от конкретной модели.
"""

from .product_variant_url_mixin import ProductVariantURLMixin
from .product_variants import ProductVariantsMixin

__all__ = [
    'ProductVariantsMixin',
    'ProductVariantURLMixin',
]
