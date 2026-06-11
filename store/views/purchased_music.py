from rest_framework.generics import ListAPIView

from common.permissions import IsListener

from store.models import ListenerAlbumAccess
from store.schema import purchased_music_schema
from store.serializers import LibraryAlbumCardSerializer


@purchased_music_schema
class PurchasedMusicView(ListAPIView):
    """Список релизов, доступных текущему слушателю."""

    permission_classes = [IsListener]
    serializer_class = LibraryAlbumCardSerializer

    def get_queryset(self):
        """Возвращает доступные текущему слушателю релизы."""
        return (
            ListenerAlbumAccess.objects
            .filter(user=self.request.user)
            .select_related(
                'album',
                'album__owner',
                'album__owner__artist_profile',
            )
            .order_by('-album__release_date', 'album__name')
        )
