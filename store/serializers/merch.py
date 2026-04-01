from rest_framework import serializers

from store.models import Merch
from store.serializers import ImageSerializer


class MerchReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Merch."""

    price = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Merch
        fields = (
            'id',
            'name',
            'description',
            'price',
            'main_image',
        )

    def get_price(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.price
        return None

    def get_main_image(self, obj):
        image = obj.images_merch.filter(is_main=True).first()
        if image:
            return image.image.url
        return None


class MerchDetailSerializer(MerchReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Merch."""

    allow_overpay = serializers.SerializerMethodField()
    images_merch = ImageSerializer(many=True, read_only=True)
    kind = serializers.StringRelatedField()
    album = serializers.StringRelatedField()

    class Meta(MerchReadSerializer.Meta):
        model = Merch
        fields = MerchReadSerializer.Meta.fields + (
            'allow_overpay',
            'images_merch',
            'kind',
            'album',
            'visibility',
            'is_published',
            'is_active',
        )

    def get_allow_overpay(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False


class MerchWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Merch."""

    class Meta:
        model = Merch
        fields = (
            'name',
            'kind',
            'price',
            'stock',
            'album',
            'descriptions',
            'image',
            'allow_overpay',
            'visibility',
        )
