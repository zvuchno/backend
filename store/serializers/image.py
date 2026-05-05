from rest_framework import serializers

from store.models import Image


class ImageSerializer(serializers.ModelSerializer):
    """Сериализатор для изображений мерча."""

    image = serializers.ImageField(use_url=True)
    is_main = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = Image
        fields = ('id', 'image', 'is_main')
