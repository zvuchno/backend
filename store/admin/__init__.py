"""Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from .album import AlbumAdmin
from .genre import GenreAdmin
from .merch import MerchAdmin
from .shopping_cart import ShoppingCartAdmin
from .track import TrackAdmin

__all__ = [
    'AlbumAdmin',
    'GenreAdmin',
    'MerchKindAdmin',
    'MerchAdmin',
    'ShoppingCartAdmin',
    'TrackAdmin',
]
