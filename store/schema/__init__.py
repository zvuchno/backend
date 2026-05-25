"""OpenAPI схемы для API приложения store.

Пакет содержит декларации схем drf-spectacular, используемых
для документирования ViewSet'. Схемы вынесены из views,
чтобы не смешивать бизнес-логику и описание API.
Каждый файл соответствует отдельному ресурсу API.
"""

from .album import album_schema
from .cart import cart_schema
from .checkout_schema import checkout_schema
from .delivery import delivery_schema
from .favorites import favorites_schema
from .genre import genre_schema
from .merch import merch_schema
from .order import order_schema
from .purchased_music import purchased_music_schema
from .sale import artist_sale_schema
from .track import track_schema

__all__ = [
    'album_schema',
    'artist_sale_schema',
    'cart_schema',
    'checkout_schema',
    'delivery_schema',
    'favorites_schema',
    'genre_schema',
    'merch_schema',
    'order_schema',
    'track_schema',
    'order_schema',
    'purchased_music_schema',
]
