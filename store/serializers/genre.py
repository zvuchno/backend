from rest_framework import serializers

from store.models import Genre


class GenreSerializer(serializers.ModelSerializer):
    """Сериализатор для Genre."""

    class Meta:
        model = Genre
        fields = ('id', 'name', 'slug')
