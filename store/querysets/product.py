from django.db import models
from django.db.models import Prefetch


class ProductQuerySet(models.QuerySet):
    """QuerySet товаров."""

    def active_content(self):
        """Возвращает товары с активным связанным контентом."""
        return self.filter(
            models.Q(
                album__isnull=False,
                album__is_active=True,
            )
            | models.Q(
                merch__isnull=False,
                merch__is_active=True,
            ),
        )

    def published_content(self):
        """Возвращает товары с опубликованным связанным контентом."""
        return self.filter(
            models.Q(
                album__isnull=False,
                album__is_active=True,
                album__is_published=True,
            )
            | models.Q(
                merch__isnull=False,
                merch__is_active=True,
                merch__is_published=True,
            ),
        )

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
