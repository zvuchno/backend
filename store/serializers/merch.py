from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, PRICE_DECIMAL_PLACES
from store.models import Image, Merch, ProductVariant
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
        for image in obj.images_merch.all():
            if image.is_main:
                return image.image.url
        return None


class VariantReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения варианта мерча."""

    characteristics = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ('id', 'sku', 'stock', 'characteristics')

    def get_characteristics(self, obj):
        return obj.characteristic or {}


class MerchDetailSerializer(MerchReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Merch."""

    allow_overpay = serializers.SerializerMethodField()
    images_merch = ImageSerializer(many=True, read_only=True)
    kind = serializers.StringRelatedField()
    album = serializers.StringRelatedField()
    variants = serializers.SerializerMethodField()

    class Meta(MerchReadSerializer.Meta):
        fields = MerchReadSerializer.Meta.fields + (
            'allow_overpay',
            'images_merch',
            'kind',
            'album',
            'visibility',
            'is_published',
            'is_active',
            'variants',
        )

    def get_allow_overpay(self, obj):
        product = getattr(obj, 'product', None)
        if product:
            return product.allow_overpay
        return False

    def get_variants(self, obj):
        product = getattr(obj, 'product', None)
        if not product:
            return []
        qs = product.variants.all().order_by('id')
        return VariantReadSerializer(qs, many=True).data


class VariantWriteSerializer(serializers.Serializer):
    """Сериализатор для записи варианта мерча."""

    id = serializers.IntegerField(required=False)
    sku = serializers.CharField(required=False, allow_blank=True)
    stock = serializers.IntegerField(min_value=0, required=True)
    characteristics = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=True,
        help_text='JSON',
    )


class MerchWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Merch."""

    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        required=True,
        write_only=True,
    )
    allow_overpay = serializers.BooleanField(required=False)
    variants = VariantWriteSerializer(many=True, required=False)
    images = ImageSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Merch
        fields = (
            'name',
            'kind',
            'price',
            'album',
            'description',
            'images',
            'allow_overpay',
            'visibility',
            'is_published',
            'is_active',
            'variants',
        )

    def validate_images(self, images):
        main_count = sum(1 for image in images if image.get('is_main'))
        if main_count > 1:
            raise serializers.ValidationError(
                'Только одно фото может быть главным.'
            )
        return images

    def to_representation(self, instance):
        return MerchDetailSerializer(instance).data

    def create(self, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        validated_data.pop('variants', None)
        images = validated_data.pop('images', [])

        merch = super().create(validated_data)

        for image in images:
            Image.objects.create(
                merch=merch,
                image=image['image'],
                is_main=image.get('is_main', False),
            )

        return merch

    def update(self, instance, validated_data):
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)
        validated_data.pop('variants', None)
        images = validated_data.pop('images', None)

        instance = super().update(instance, validated_data)

        if images is not None:
            existing = {img.id: img for img in instance.images_merch.all()}
            incoming_ids = {img['id'] for img in images if img.get('id')}

            for img_id, img in existing.items():
                if img_id not in incoming_ids:
                    img.delete()

            for image in images:
                img_id = image.get('id')
                if img_id and img_id in existing:
                    obj = existing[img_id]
                    changed = False
                    if 'is_main' in image and obj.is_main != image['is_main']:
                        obj.is_main = image['is_main']
                        changed = True
                    if 'image' in image and obj.image != image['image']:
                        obj.image = image['image']
                        changed = True
                    if changed:
                        obj.save()
                else:
                    Image.objects.create(
                        merch=instance,
                        image=image['image'],
                        is_main=image.get('is_main', False),
                    )

        return instance
