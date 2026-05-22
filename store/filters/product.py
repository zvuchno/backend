import django_filters
from django.db import models

from store.models import Product


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
    genre = django_filters.CharFilter(method='filter_genre')
    ordering = django_filters.CharFilter(method='filter_ordering')

    class Meta:
        model = Product
        fields = (
            'type',
            'genre',
            'ordering',
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

    def filter_genre(self, queryset, name, value):
        """Фильтрует товары по жанру музыкального контента."""
        if not value:
            return queryset

        return queryset.filter(
            models.Q(
                product_type=Product.ProductType.ALBUM,
                album__genre__slug=value,
            )
            | models.Q(
                product_type=Product.ProductType.MERCH,
                merch__is_carrier=True,
                merch__album__genre__slug=value,
            ),
        )
