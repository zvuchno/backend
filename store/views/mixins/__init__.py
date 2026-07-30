"""Модуль миксинов для представлений.

Содержит переиспользуемые классы-поведения (mixins), которые можно подключать
к различным ViewSet. Эти миксины инкапсулируют общие действия и логику,
не зависящие от конкретной модели.
"""

from .commerce import ProductActionMixin
from .managed_artist import ManagedArtistActionMixin
from .music_access import PurchasedMusicAccessMixin
from .soft_delete import SoftDeleteMixin
from .track import TrackReadQuerysetMixin

__all__ = [
    'ManagedArtistActionMixin',
    'PurchasedMusicAccessMixin',
    'ProductActionMixin',
    'SoftDeleteMixin',
    'TrackReadQuerysetMixin',
]
