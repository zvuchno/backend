"""Фильтры для треков."""

from django_filters import rest_framework as filters

from store.models import Track


class TrackFilter(filters.FilterSet):
    """Набор фильтров для модели Треков."""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    genre = filters.CharFilter(field_name='album__genre__slug')
    album = filters.NumberFilter(field_name='album_id')
    artist = filters.CharFilter(
        field_name='album__owner__artist_profile__slug',
    )

    class Meta:
        model = Track
        fields = ('album', 'name', 'genre', 'artist')
