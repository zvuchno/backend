from rest_framework import serializers

from store.models import Image


class ImageSerializer(serializers.ModelSerializer):
    """Сериализатор для изображений мерча."""

    class Meta:
        model = Image
        fields = ('image', 'merch')
