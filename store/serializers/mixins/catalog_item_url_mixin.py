from django.urls import reverse


class CatalogTargetURLMixin:
    """Миксин для формирования ссылок каталожных карточек."""

    def get_target_url(self, obj) -> str | None:
        """Возвращает ссылку на карточку альбома."""
        if obj.product_type == 'album':
            return reverse(
                'api:store:albums-detail',
                kwargs={'pk': obj.album_id},
            )
        if obj.product_type == 'merch':
            return reverse(
                'api:store:merch-detail',
                kwargs={'pk': obj.merch_id},
            )
        return None
