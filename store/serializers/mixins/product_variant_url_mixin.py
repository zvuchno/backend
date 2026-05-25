from django.urls import reverse


class ProductVariantURLMixin:
    """Миксин для формирования target_url."""

    def get_target_url(self, obj) -> str:
        """Возвращает URL для объекта в API."""
        if hasattr(obj, 'product_variant'):
            obj = obj.product_variant

        product = obj.product

        if product.album_id:
            relative = reverse(
                'api:store:albums-detail',
                kwargs={'pk': product.album_id},
            )
        elif product.track_id:
            relative = reverse(
                'api:store:tracks-detail',
                kwargs={'pk': product.track_id},
            )
        elif product.merch_id:
            relative = reverse(
                'api:store:merch-detail',
                kwargs={'pk': product.merch_id},
            )
        else:
            return None

        request = (
            self.context.get('request') if hasattr(self, 'context') else None
        )
        if request:
            return request.build_absolute_uri(relative)

        return relative
