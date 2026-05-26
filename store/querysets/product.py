from django.db import models
from django.db.models import Prefetch


class ProductQuerySet(models.QuerySet):
    """QuerySet товаров."""

    def with_content(self):
        """Подтягивает связанные контентные объекты товара."""
        return self.select_related(
            'album',
            'album__owner',
            'album__owner__artist_profile',
            'merch',
            'merch__owner',
            'merch__owner__artist_profile',
            'merch__kind',
            'track',
            'track__owner',
            'track__owner__artist_profile',
        )

    def with_card_data(self):
        """Подтягивает данные для карточек каталога."""
        from store.models.product_variant import ProductVariant

        return self.with_content().prefetch_related(
            'merch__images_merch',
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.filter(
                    is_active=True,
                ).order_by('id'),
                to_attr='active_variants',
            ),
        )

    def active(self):
        """Возвращает активные товары."""
        return self.filter(is_active=True)
