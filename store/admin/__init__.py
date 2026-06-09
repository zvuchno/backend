"""Административная конфигурация моделей музыкального каталога.

Определяет регистрацию моделей и настройки их отображения
в интерфейсе Django Admin.
"""

from django.contrib import admin

from .album import AlbumAdmin
from .cart import CartAdmin
from .delivery import DeliveryAdmin
from .favorite import FavoriteAdmin
from .genre import GenreAdmin
from .merch import MerchAdmin
from .merch_kind import MerchKindAdmin
from .order import OrderAdmin
from .promocode import PromocodeAdmin
from .track import TrackAdmin

__all__ = [
    'AlbumAdmin',
    'CartAdmin',
    'DeliveryAdmin',
    'FavoriteAdmin',
    'GenreAdmin',
    'MerchKindAdmin',
    'MerchAdmin',
    'OrderAdmin',
    'PromocodeAdmin',
    'TrackAdmin',
]

# Заголовок страницы (вкладка браузера)
admin.site.site_title = 'ZVUCHNO'
# Заголовок на самой странице
admin.site.site_header = 'ZVUCHNO Администрирование'
