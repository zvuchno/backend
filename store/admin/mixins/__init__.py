"""Модуль миксинов для админки Django.

Содержит переиспользуемые классы-поведения (mixins), которые можно подключать
к различным ModelAdmin. Эти миксины инкапсулируют общие действия и логику,
не зависящие от конкретной модели.
"""

from .auto_owner_mixin import AutoOwnerAdminMixin
from .commerce import CommerceMixin

__all__ = [
    'AutoOwnerAdminMixin',
    'CommerceMixin',
]
