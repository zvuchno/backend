from django.urls import reverse


class ProductVariantURLMixin:
    """Миксин для формирования target_url."""

    def get_target_url(self, obj) -> str | None:
        """Возвращает URL для объекта в API."""
        if hasattr(obj, 'product_variant'):
            obj = obj.product_variant

        product = obj.product

        if product.album_id:
            return reverse(
                'api:store:albums-detail',
                kwargs={'pk': product.album_id},
            )
        if product.track_id:
            return reverse(
                'api:store:tracks-detail',
                kwargs={'pk': product.track_id},
            )
        if product.merch_id:
            return reverse(
                'api:store:merch-detail',
                kwargs={'pk': product.merch_id},
            )
        return None
