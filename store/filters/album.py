"""Фильтры для альбомов."""

from django_filters import rest_framework as filters

from store.models import Album


class AlbumFilter(filters.FilterSet):
    """Набор фильтров для модели Альбомов."""

    genre = filters.NumberFilter(field_name='genre_id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    artist_id = filters.NumberFilter(field_name='owner__artist_profile__id')
    artist_name = filters.CharFilter(
        field_name='owner__artist_profile__name',
        lookup_expr='icontains',
    )

    class Meta:
        model = Album
        fields = ('genre', 'name', 'artist_id', 'artist_name')
