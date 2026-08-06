"""Фильтры для альбомов."""

import django_filters
from django_filters import rest_framework as filters

from store.models import Album


class AlbumFilter(filters.FilterSet):
    """Набор фильтров для модели Альбомов."""

    genre = filters.BaseInFilter(field_name='genre__slug', lookup_expr='in')

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

    artist_id = django_filters.NumberFilter()

    artist_slug = filters.BaseInFilter(
        field_name='artist__slug',
        lookup_expr='in',
    )

    class Meta:
        model = Album
        fields = ('genre', 'name', 'artist_id', 'artist_slug')
