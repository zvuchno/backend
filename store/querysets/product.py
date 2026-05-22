from django.db import models
from django.db.models import BooleanField, Exists, OuterRef, Value

PRODUCT_TYPES = {'album', 'merch'}
CATALOG_ALL = 'all'


class ProductQuerySet(models.QuerySet):
    """QuerySet товаров."""

    def visible_for_catalog(self):
        """Возвращает товары с активным публичным контентом."""
        return self.filter(
            models.Q(
                product_type='album',
                album__is_active=True,
                album__is_published=True,
                album__visibility='public',
            )
            | models.Q(
                product_type='merch',
                merch__is_active=True,
                merch__is_published=True,
                merch__visibility='public',
            ),
        )

    # def by_type(self, product_type):
    #     """Фильтрует товары по типу."""
    #     if not product_type or product_type == CATALOG_ALL:
    #         return self
    #
    #     if product_type not in PRODUCT_TYPES:
    #         return self.none()
    #
    #     return self.filter(product_type=product_type)

    def with_content(self):
        """Подтягивает связанные сущности товара."""
        return self.select_related(
            'album',
            'album__owner',
            'album__owner__artist_profile',
            'album__genre',
            'merch',
            'merch__owner',
            'merch__owner__artist_profile',
            'merch__album__genre',
            'merch__kind',
        ).prefetch_related(
            'merch__images_merch',
        )

    def with_is_favorite(self, user):
        """Добавляет признак наличия варианта товара в избранном."""
        if not user.is_authenticated:
            return self.annotate(
                is_favorite=Value(False, output_field=BooleanField()),
            )

        from store.models import Favorite

        favorite_variants = Favorite.objects.filter(
            user=user,
            product_variant__product_id=OuterRef('pk'),
        )

        return self.annotate(
            is_favorite=Exists(favorite_variants),
        )
