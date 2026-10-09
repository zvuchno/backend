"""Фильтры для бонусов."""

from django_filters import rest_framework as filters

from store.models import Bonus


class BonusFilter(filters.FilterSet):
    """Фильтр для модели Бонусов."""

    album = filters.NumberFilter(field_name='album_id')

    class Meta:
        model = Bonus
        fields = ('album',)
