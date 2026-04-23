"""Фильтры для мерча."""

from django_filters import rest_framework as filters

from store.models import Merch


class MerchFilter(filters.FilterSet):
    """Набор фильтров для модели Мерча."""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    kind = filters.CharFilter(field_name='kind__slug', lookup_expr='icontains')
    album = filters.NumberFilter(field_name='album_id')
    artist = filters.CharFilter(
        field_name='owner__artist_profile__slug',
        lookup_expr='icontains',
    )

    class Meta:
        model = Merch
        fields = ('name', 'kind', 'album', 'artist')
