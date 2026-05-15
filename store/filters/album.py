"""Фильтры для альбомов."""

from django_filters import rest_framework as filters

from store.models import Album


class AlbumFilter(filters.FilterSet):
    """Набор фильтров для модели Альбомов."""

    genre = filters.CharFilter(field_name='genre__slug')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    artist = filters.CharFilter(field_name='owner__artist_profile__slug')

    class Meta:
        model = Album
        fields = ('genre', 'name', 'artist')
