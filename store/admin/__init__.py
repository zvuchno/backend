"""Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from .album import AlbumAdmin
from .genre import GenreAdmin
from .kind import KindAdmin
from .merch import MerchAdmin
from .track import TrackAdmin

__all__ = [
    'AlbumAdmin',
    'GenreAdmin',
    'KindAdmin',
    'MerchAdmin',
    'TrackAdmin',
]
