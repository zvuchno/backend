"""Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from .album import AlbumAdmin
from .cart import CartAdmin
from .delivery import Delivery
from .genre import GenreAdmin
from .merch import MerchAdmin
from .merch_kind import MerchKindAdmin
from .track import TrackAdmin

__all__ = [
    'AlbumAdmin',
    'Delivery',
    'GenreAdmin',
    'MerchKindAdmin',
    'MerchAdmin',
    'CartAdmin',
    'TrackAdmin',
]
