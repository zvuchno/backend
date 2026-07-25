"""Фильтры для артистов."""

import django_filters

from users.models import ArtistProfile, ArtistProfileType


class ArtistFilter(django_filters.FilterSet):
    """Фильтр по жанру."""

    genre = django_filters.CharFilter(method='filter_by_genre')
    label = django_filters.CharFilter(
        field_name='label__slug',
        lookup_expr='exact',
    )
    profile_type = django_filters.ChoiceFilter(
        choices=ArtistProfileType.choices,
    )

    class Meta:
        model = ArtistProfile
        fields = ('label', 'profile_type')

    def filter_by_genre(self, queryset, name, value):
        """Фильтрация по жанрам альбомов артиста."""
        return queryset.filter(user__album_set__genre__slug=value).distinct()
