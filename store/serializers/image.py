from rest_framework import serializers

from store.models.image import Image


class ImageSerializer(serializers.ModelSerializer):
    """Сериализатор для фотографий."""

    class Meta:
        model = Image
        fields = ('id', 'image')
