"""Модуль миксинов для админки Django.

Содержит переиспользуемые классы-поведения (mixins), которые можно подключать
к различным ModelAdmin. Эти миксины инкапсулируют общие действия и логику,
не зависящие от конкретной модели.
"""

from .auto_created_by_mixin import AutoCreatedByAdminMixin
from .commerce import CommerceBaseMixin, CommerceDisplayMixin

__all__ = [
    'AutoCreatedByAdminMixin',
    'CommerceBaseMixin',
    'CommerceDisplayMixin',
]
