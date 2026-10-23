"""Фильтры для треков."""

from django_filters import rest_framework as filters

from store.models import ReleaseTrack


class TrackFilter(filters.FilterSet):
    """Набор фильтров для модели Треков."""

    name = filters.CharFilter(
        field_name='recording__name',
        lookup_expr='icontains',
    )
    genre = filters.CharFilter(field_name='release__genre__slug')
    album = filters.NumberFilter(field_name='release_id')
    artist = filters.CharFilter(
        field_name='release__artist__slug',
    )

    class Meta:
        model = ReleaseTrack
        fields = ('album', 'name', 'genre', 'artist')
