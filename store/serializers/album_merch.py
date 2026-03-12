from rest_framework import serializers

from store.models.album_merch import AlbumMerch


class AlbumMerchSerializer(serializers.ModelSerializer):
    """Сериализатор связи альбома и мерча."""

    album = serializers.StringRelatedField()
    merch = serializers.StringRelatedField()

    class Meta:
        model = AlbumMerch
        fields = ('album', 'merch')
