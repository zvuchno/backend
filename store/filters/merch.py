"""Фильтры для мерча."""

from django_filters import rest_framework as filters

from store.models import Merch


class MerchFilter(filters.FilterSet):
    """Набор фильтров для модели Мерча."""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

    kind = filters.BaseInFilter(field_name='kind__slug', lookup_expr='in')

    album = filters.BaseInFilter(field_name='album_id', lookup_expr='in')

    artist = filters.BaseInFilter(
        field_name='owner__artist_profile__slug',
        lookup_expr='in',
    )

    class Meta:
        model = Merch
        fields = ('name', 'kind', 'album', 'artist')
