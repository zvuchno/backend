"""Модуль миксинов для представлений.

Содержит переиспользуемые классы-поведения (mixins), которые можно подключать
к различным ViewSet. Эти миксины инкапсулируют общие действия и логику,
не зависящие от конкретной модели.
"""

from .commerce import ProductActionMixin
from .soft_delete import SoftDeleteMixin

__all__ = [
    'ProductActionMixin',
    'SoftDeleteMixin',
]
