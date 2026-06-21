from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsListener

from store.models import AlbumArchive, ListenerAlbumAccess, ListenerTrackAccess
from store.schema import (
    purchased_music_download_detail_schema,
    purchased_music_schema,
)
from store.serializers import (
    LibraryAlbumCardSerializer,
    PurchasedMusicDLDetailSerializer,
)
from store.services.album_archive import AlbumArchiveScheduler


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


@purchased_music_download_detail_schema
class PurchasedMusicDLDetailView(APIView):
    """Варианты скачивания одного доступного слушателю релиза."""

    permission_classes = [IsListener]

    def get(self, request, album_id):
        """Возвращает архив и доступные отдельные треки."""
        album_access = get_object_or_404(
            ListenerAlbumAccess.objects.select_related('album'),
            user=request.user,
            album_id=album_id,
        )
        album = album_access.album

        track_accesses = (
            ListenerTrackAccess.objects
            .filter(
                user=request.user,
                track__album_id=album.id,
            )
            .select_related('track')
            .order_by('track__position', 'track__id')
        )

        items = []

        if album_access.is_fully_available:
            archive_item = self._get_archive_item(album)

            if archive_item is not None:
                items.append(archive_item)

        items.extend(
            self._get_track_item(access.track) for access in track_accesses
        )

        serializer = PurchasedMusicDLDetailSerializer(
            {
                'album_id': album.id,
                'access': (
                    'full' if album_access.is_fully_available else 'partial'
                ),
                'items': items,
            },
        )
        return Response(serializer.data)

    @staticmethod
    def _get_archive_item(album) -> dict | None:
        """Проверяет состояние архива и возвращает item для интерфейса."""
        AlbumArchiveScheduler.schedule(album)

        archive = (
            AlbumArchive.objects
            .filter(album=album)
            .only('album_id', 'status')
            .first()
        )

        if archive is None:
            return None

        return {
            'type': 'archive',
            'id': album.id,
            'title': 'Скачать альбом в .ZIP',
            'status': archive.status,
        }

    @staticmethod
    def _get_track_item(track) -> dict:
        """Возвращает item отдельного доступного трека."""
        if track.position is None:
            title = track.name
        else:
            title = f'{track.position:02d}. {track.name}'

        return {
            'type': 'track',
            'id': track.id,
            'title': title,
            'status': 'ready',
        }
