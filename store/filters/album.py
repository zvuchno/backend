"""Фильтры для альбомов."""

from django_filters import rest_framework as filters

from store.models import Album


class AlbumFilter(filters.FilterSet):
    """Набор фильтров для модели Альбомов."""

    genre = filters.BaseInFilter(field_name='genre__slug', lookup_expr='in')

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

    artist = filters.BaseInFilter(
        field_name='owner__artist_profile__slug',
        lookup_expr='in',
    )

    class Meta:
        model = Album
        fields = ('genre', 'name', 'artist')
