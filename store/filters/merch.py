"""Фильтры для мерча."""

from django.db import models
from django_filters import rest_framework as filters

from store.constants import CHAR_PRESET_SIMPLE
from store.models import Merch


class MerchFilter(filters.FilterSet):
    """Набор фильтров для модели Мерча."""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    kind = filters.BaseInFilter(field_name='kind__slug', lookup_expr='in')
    album = filters.BaseInFilter(field_name='album_id', lookup_expr='in')
    artist = filters.BaseInFilter(
        field_name='artist__slug',
        lookup_expr='in',
    )
    in_stock = filters.BooleanFilter(method='filter_in_stock')

    class Meta:
        model = Merch
        fields = ('name', 'kind', 'album', 'artist')

    def filter_in_stock(self, queryset, name, value):
        has_prop_stock = (
            ~models.Q(product__property_name='')
            & models.Q(product__variants__stock__gt=0)
            & ~models.Q(product__variants__property_value=CHAR_PRESET_SIMPLE)
        )
        no_prop_stock = (
            models.Q(product__property_name='')
            & models.Q(product__variants__stock__gt=0)
            & models.Q(product__variants__property_value=CHAR_PRESET_SIMPLE)
        )
        in_stock_condition = has_prop_stock | no_prop_stock

        if value:
            return queryset.filter(in_stock_condition).distinct()

        in_stock_ids = queryset.filter(in_stock_condition).values('id')
        return queryset.exclude(id__in=in_stock_ids)
