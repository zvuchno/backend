"""Кастомная пагинация API."""

from rest_framework.pagination import LimitOffsetPagination

from config.constants import (
    DEFAULT_PAGINATION_LIMIT,
    MAX_PAGINATION_LIMIT,
    MAX_RANDOM_LIMIT,
)


class DefaultLimitOffsetPagination(LimitOffsetPagination):
    """Пагинация по умолчанию для ручек со списками."""

    default_limit = DEFAULT_PAGINATION_LIMIT
    max_limit = MAX_PAGINATION_LIMIT
    random_limit = MAX_RANDOM_LIMIT

    def get_limit(self, request):
        """Возвращает limit с ограничением для случайной выдачи."""
        limit = super().get_limit(request)

        if request.query_params.get('ordering') == 'random':
            if limit is None:
                return self.random_limit

            return min(limit, self.random_limit)

        return limit
