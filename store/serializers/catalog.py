from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.serializers.mixins import CatalogTargetURLMixin


class CatalogBaseSerializer(
    CatalogTargetURLMixin,
    serializers.Serializer,
):
    """Базовый сериализатор карточки смешанного каталога."""

    type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True, required=False)
    image = serializers.CharField(allow_null=True)
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        allow_null=True,
        required=False,
    )
    target_url = serializers.CharField()
    created_at = serializers.DateTimeField()

    def get_artist_name(self, owner) -> str:
        """Возвращает имя артиста-владельца."""
        artist = getattr(owner, 'artist_profile', None)
        return artist.name if artist else ''

    def get_image_url(self, obj) -> str | None:
        """Возвращает URL изображения карточки."""
        # Album
        if hasattr(obj, 'cover_image'):
            return obj.cover_image.url if obj.cover_image else None

        # Merch
        if hasattr(obj, 'images_merch'):
            images = list(obj.images_merch.all())
            main_image = next(
                (image for image in images if image.is_main),
                None,
            )
            image = main_image or (images[0] if images else None)
            if image and image.image:
                return image.image.url
        return None


class CatalogAlbumSerializer(CatalogBaseSerializer):
    """Сериализатор альбомов для смешанного каталога."""

    type = serializers.CharField(default='album')
    title = serializers.CharField(source='name')
    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        allow_null=True,
    )
    subtitle = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    target_url = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    def get_subtitle(self, obj):
        return self.get_artist_name(obj.owner)

    def get_image(self, obj):
        return self.get_image_url(obj)

    def get_target_url(self, obj):
        return self.get_album_target_url(obj)


class CatalogCarrierSerializer(CatalogBaseSerializer):
    """Сериализатор носителей для смешанного каталога."""

    type = serializers.CharField(default='carrier')
    title = serializers.CharField(source='name')
    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        allow_null=True,
    )
    subtitle = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    target_url = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    def get_subtitle(self, obj):
        return self.get_artist_name(obj.owner)

    def get_image(self, obj):
        return self.get_image_url(obj)

    def get_target_url(self, obj):
        return self.get_merch_target_url(obj)


class CatalogMerchSerializer(CatalogBaseSerializer):
    """Сериализатор мерча для смешанного каталога."""

    type = serializers.CharField(default='merch')
    title = serializers.CharField(source='name')
    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        allow_null=True,
    )
    subtitle = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    target_url = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    def get_subtitle(self, obj):
        return self.get_artist_name(obj.owner)

    def get_image(self, obj):
        return self.get_image_url(obj)

    def get_target_url(self, obj):
        return self.get_merch_target_url(obj)
