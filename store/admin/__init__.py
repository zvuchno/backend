"""Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from .album import AlbumAdmin
from .carrier import Carrier
from .category import CategoryAdmin
from .genre import GenreAdmin
from .kind import KindAdmin
from .merch import MerchAdmin
from .track import TrackAdmin

__all__ = [
    'AlbumAdmin',
    'Carrier',
    'CategoryAdmin',
    'GenreAdmin',
    'KindAdmin',
    'MerchAdmin',
    'TrackAdmin',
]
