"""Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from .album import AlbumAdmin
from .cart import CartAdmin
from .delivery import DeliveryAdmin
from .genre import GenreAdmin
from .merch import MerchAdmin
from .merch_kind import MerchKindAdmin
from .order import OrderAdmin
from .track import TrackAdmin

__all__ = [
    'AlbumAdmin',
    'CartAdmin',
    'DeliveryAdmin',
    'GenreAdmin',
    'MerchKindAdmin',
    'MerchAdmin',
    'OrderAdmin',
    'TrackAdmin',
]
