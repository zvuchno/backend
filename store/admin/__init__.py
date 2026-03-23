"""Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from .album import AlbumAdmin
from .category import CategoryAdmin
from .genre import GenreAdmin
from .merch import MerchAdmin
from .merch_kind import KindAdmin
from .track import TrackAdmin

__all__ = [
    'AlbumAdmin',
    'CategoryAdmin',
    'GenreAdmin',
    'KindAdmin',
    'MerchAdmin',
    'TrackAdmin',
]
