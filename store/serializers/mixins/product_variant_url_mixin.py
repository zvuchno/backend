from django.urls import reverse


class ProductVariantURLMixin:
    """Миксин для формирования target_url."""

    def get_target_url(self, obj) -> str | None:

        target_type = getattr(obj, 'target_type', None)
        target_id = getattr(obj, 'target_id', None)

        if not target_type or not target_id:
            return None

        if target_type == 'album':
            return reverse(
                'api:store:albums-detail',
                kwargs={'pk': target_id},
            )

        if target_type == 'merch':
            return reverse(
                'api:store:merch-detail',
                kwargs={'pk': target_id},
            )

        return None
