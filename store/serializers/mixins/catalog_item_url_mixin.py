from django.urls import reverse

from store.models import Product


class CatalogTargetURLMixin:
    """Миксин для формирования ссылок каталожных карточек."""

    def get_target_url(self, obj) -> str | None:
        """Возвращает ссылку на карточку альбома."""
        if obj.product_type == Product.ProductType.ALBUM:
            return reverse(
                'api:store:albums-detail',
                kwargs={'pk': obj.album_id},
            )
        if obj.product_type == Product.ProductType.MERCH:
            return reverse(
                'api:store:merch-detail',
                kwargs={'pk': obj.merch_id},
            )
        if obj.product_type == Product.ProductType.TRACK:
            return reverse(
                'api:store:tracks-detail',
                kwargs={'pk': obj.track_id},
            )
        return None
