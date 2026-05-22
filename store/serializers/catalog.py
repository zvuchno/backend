from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Product
from store.serializers.mixins import CatalogTargetURLMixin


class ProductCatalogListSerializer(
    CatalogTargetURLMixin,
    serializers.ModelSerializer,
):
    """Сериализатор карточки товара в каталоге."""

    type = serializers.CharField(source='product_type')
    product_kind = serializers.SerializerMethodField()
    object_id = serializers.IntegerField(source='content_id')
    name = serializers.CharField()
    image = serializers.SerializerMethodField()
    artist = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        allow_null=True,
        required=False,
    )
    target_url = serializers.SerializerMethodField()
    is_favorite = serializers.BooleanField(default=False)

    class Meta:
        model = Product
        fields = (
            'id',
            'type',
            'product_kind',
            'name',
            'object_id',
            'image',
            'artist',
            'price',
            'target_url',
            'is_favorite',
        )

    def get_product_kind(self, obj) -> str | None:
        if obj.merch:
            return obj.merch.kind.name
        if obj.album:
            return 'Сингл' if obj.album.is_single else 'Альбом'
        return None

    def get_artist(self, obj) -> str:
        """Возвращает имя артиста-владельца."""
        artist = getattr(obj.owner, 'artist_profile', None)
        return artist.name if artist else ''

    def get_image(self, obj) -> str | None:
        """Возвращает URL изображения карточки."""
        content = obj.content

        if content is None:
            return None

        if hasattr(content, 'cover_image') and content.cover_image:
            return content.cover_image.url

        if hasattr(content, 'images_merch'):
            images = list(content.images_merch.all())
            main_image = next(
                (image for image in images if image.is_main),
                None,
            )
            image = main_image or (images[0] if images else None)

            if image and image.image:
                return image.image.url

        return None
