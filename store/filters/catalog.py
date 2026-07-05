import django_filters
from django.db import models

from store.models import Product


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    """Фильтр по списку строк через запятую."""


class ProductCatalogFilter(django_filters.FilterSet):
    """Фильтры каталога товаров."""

    type = django_filters.ChoiceFilter(
        method='filter_type',
        choices=(
            ('all', 'Все'),
            (Product.ProductType.ALBUM, 'Альбомы'),
            (Product.ProductType.MERCH, 'Мерч'),
        ),
    )
    genre = CharInFilter(method='filter_genre')
    kind = CharInFilter(method='filter_kind')
    ordering = django_filters.CharFilter(method='filter_ordering')
    artist = django_filters.CharFilter(method='filter_artist')

    class Meta:
        model = Product
        fields = (
            'type',
            'genre',
            'kind',
            'artist',
            'ordering',
        )

    def filter_artist(self, queryset, name, value):
        """Фильтрует товары по slug артиста."""
        if not value:
            return queryset

        return queryset.filter(
            models.Q(
                product_type=Product.ProductType.ALBUM,
                album__owner__artist_profile__slug=value,
            )
            | models.Q(
                product_type=Product.ProductType.MERCH,
                merch__owner__artist_profile__slug=value,
            ),
        )

    def filter_ordering(self, queryset, name, value):
        """Сортирует товары каталога."""
        if value == 'random':
            return queryset.order_by('?')

        if value == 'created_at':
            return queryset.order_by('catalog_created_at', 'pk')

        return queryset.order_by('-catalog_created_at', '-pk')

    def filter_type(self, queryset, name, value):
        """Фильтрует товары по типу."""
        if not value or value == 'all':
            return queryset

        return queryset.filter(product_type=value)

    def filter_genre(self, queryset, name, values):
        """Фильтрует товары по slug жанров музыкального контента.

        Для альбомов жанр берется с album.genre.
        Для носителей жанр берется с привязанного merch.album.genre.
        Обычный мерч без альбома при фильтре по жанру не попадает.
        """
        if not values:
            return queryset

        return queryset.filter(
            models.Q(
                product_type=Product.ProductType.ALBUM,
                album__genre__slug__in=values,
            )
            | models.Q(
                product_type=Product.ProductType.MERCH,
                merch__kind__is_carrier=True,
                merch__album__genre__slug__in=values,
            ),
        )

    def filter_kind(self, queryset, name, values):
        """Фильтрует мерч по slug типа товара."""
        if not values:
            return queryset

        return queryset.filter(
            product_type=Product.ProductType.MERCH,
            merch__kind__slug__in=values,
        )
