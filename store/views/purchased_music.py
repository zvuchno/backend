from rest_framework.generics import RetrieveAPIView

from common.permissions import IsListener

from store.models import (
    Album,
    ListenerTrackAccess,
    Track,
)
from store.schema import purchased_music_schema
from store.serializers import PurchasedMusicSerializer


@purchased_music_schema
class PurchasedMusicView(RetrieveAPIView):
    """Библиотека купленной музыки текущего слушателя."""

    permission_classes = [IsListener]
    serializer_class = PurchasedMusicSerializer

    def get_object(self):
        track_ids = list(
            ListenerTrackAccess.objects.filter(
                user=self.request.user,
            ).values_list('track_id', flat=True),
        )

        albums = Album.objects.fully_available_for_track_ids(track_ids)

        album_ids = list(albums.values_list('id', flat=True))

        tracks = Track.objects.filter(id__in=track_ids).exclude(
            album_id__in=album_ids,
        )

        return {
            'albums': albums,
            'tracks': tracks,
        }
