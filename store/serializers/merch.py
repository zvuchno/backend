from rest_framework import serializers

from store.models.album import Album
from store.models.image import Image
from store.models.merch import Merch
from store.serializers.album_merch import AlbumMerchSerializer
from store.serializers.image import ImageSerializer


class MerchReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Merch."""

    category = serializers.StringRelatedField()
    kind = serializers.StringRelatedField()
    owner = serializers.StringRelatedField()
    images_merch = ImageSerializer(many=True)
    album_merch = AlbumMerchSerializer(many=True)

    class Meta:
        model = Merch
        fields = (
            'id',
            'category',
            'name',
            'price',
            'allow_fans_overpay',
            'quantity',
            'kind',
            'description',
            'owner',
            'visibility',
            'characteristic',
            'images_merch',
            'album_merch',
        )


class MerchWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи Merch."""

    images_merch = ImageSerializer(many=True)

    class Meta:
        model = Merch
        fields = (
            'category',
            'name',
            'price',
            'allow_fans_overpay',
            'quantity',
            'kind',
            'description',
            'visibility',
            'characteristic',
            'images_merch',
            'album',
        )

    def create(self, validated_data):
        image_file = validated_data.pop('images_merch')
        merch = Merch.objects.create(**validated_data)
        for image in image_file:
            Image.objects.create(merch=merch, image=image['image'])

        album = self.initial_data.get('album')
        if album:
            album_obj = Album.objects.get(id=album)
            merch.album.add(album_obj)
        return merch
