"""Фильтры для артистов."""

import django_filters

from users.models import ArtistProfile


class ArtistFilter(django_filters.FilterSet):
    """Фильтр по жанру."""

    genre = django_filters.CharFilter(method='filter_by_genre')

    class Meta:
        model = ArtistProfile
        fields = ()

    def filter_by_genre(self, queryset, name, value):
        """Фильтрация по жанрам альбомов артиста."""
        return queryset.filter(user__album_set__genre__slug=value).distinct()
