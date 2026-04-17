"""Модуль фильтрации данных (Query Filters).

Содержит классы FilterSet для обработки параметров запроса в API.
"""

from .album import AlbumFilter

__all__ = [
    'AlbumFilter',
]
