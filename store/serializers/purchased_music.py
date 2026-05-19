from rest_framework import serializers

from store.models import Album, Track


class LibraryTrackSerializer(serializers.ModelSerializer):
    """Сериализатор купленного трека."""

    download_url = serializers.URLField(default=None)

    class Meta:
        model = Track
        fields = (
            'id',
            'name',
            'album',
            'duration',
            'download_url',
        )


class LibraryAlbumSerializer(serializers.ModelSerializer):
    """Сериализатор купленного альбома."""

    download_url = serializers.URLField(default=None)

    class Meta:
        model = Album
        fields = (
            'id',
            'name',
            'is_single',
            'release_date',
            'genre',
            'description',
            'cover_image',
            'download_url',
        )


class PurchasedMusicSerializer(serializers.Serializer):
    """Сериализатор купленной музыки слушателя."""

    albums = LibraryAlbumSerializer(many=True)
    tracks = LibraryTrackSerializer(many=True)
