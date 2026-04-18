"""Фильтры для мерча."""

from django_filters import rest_framework as filters

from store.models import Merch


class MerchFilter(filters.FilterSet):
    """Набор фильтров для модели Мерча."""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    kind = filters.NumberFilter(field_name='kind_id')
    album = filters.NumberFilter(field_name='album_id')
    artist_id = filters.NumberFilter(field_name='owner__artist_profile__id')
    artist_name = filters.CharFilter(
        field_name='owner__artist_profile__name',
        lookup_expr='icontains',
    )

    class Meta:
        model = Merch
        fields = ('name', 'kind', 'album', 'artist_id', 'artist_name')
