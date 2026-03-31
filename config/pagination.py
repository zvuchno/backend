"""Кастомная пагинация API."""

from rest_framework.pagination import LimitOffsetPagination

from config.constants import (
    DEFAULT_PAGINATION_LIMIT,
    MAX_PAGINATION_LIMIT,
)


class DefaultLimitOffsetPagination(LimitOffsetPagination):
    """Пагинация по умолчанию для ручек со списками."""

    default_limit = DEFAULT_PAGINATION_LIMIT
    max_limit = MAX_PAGINATION_LIMIT
