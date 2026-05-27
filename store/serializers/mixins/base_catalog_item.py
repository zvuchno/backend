from decimal import Decimal


class BaseCatalogItemSerializerMixin:
    """Миксин для общих полей мерча и альбомов в каталоге."""

    class Meta:
        fields = (
            'id',
            'artist_name',
            'kind',
            'year',
            'name',
            'price',
            'image',
            'product_type',
        )

    def get_price(self, obj) -> Decimal | None:
        product = getattr(obj, 'product', None)
        if product:
            return product.price
        return None

    def get_artist_name(self, obj):
        owner = getattr(obj, 'owner', None)
        if not owner:
            return None
        artist_profile = getattr(owner, 'artist_profile', None)
        return artist_profile.name if artist_profile else None
