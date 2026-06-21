from rest_framework import status
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsListener

from store.models import (
    AlbumArchive,
    ListenerAlbumAccess,
    ListenerTrackAccess,
)
from store.schema import (
    archive_download_link_schema,
    purchased_music_download_detail_schema,
    purchased_music_schema,
    track_download_link_schema,
)
from store.serializers import (
    DownloadLinkSerializer,
    LibraryAlbumCardSerializer,
    PurchasedMusicDLDetailSerializer,
)
from store.services import (
    DownloadFilenameService,
    DownloadLinkService,
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
        """Возвращает варианты скачивания доступного релиза."""
        album_access = get_object_or_404(
            ListenerAlbumAccess.objects.select_related(
                'album',
                'album__owner',
                'album__owner__artist_profile',
            ),
            user=request.user,
            album_id=album_id,
        )

        track_accesses = (
            ListenerTrackAccess.objects
            .filter(
                user=request.user,
                track__album_id=album_access.album_id,
            )
            .select_related('track')
            .order_by('track__position', 'track__id')
        )

        tracks = [track_access.track for track_access in track_accesses]

        archive = None

        if album_access.is_fully_available:
            AlbumArchiveScheduler.schedule(album_access.album)

            archive = (
                AlbumArchive.objects
                .filter(album_id=album_access.album_id)
                .only('album_id', 'status')
                .first()
            )

        serializer = PurchasedMusicDLDetailSerializer(
            album_access,
            context={
                'request': request,
                'tracks': tracks,
                'archive': archive,
            },
        )
        return Response(serializer.data)


@track_download_link_schema
class PurchasedMusicTrackDownloadLinkView(APIView):
    """Выдаёт временную ссылку на доступный пользователю трек."""

    permission_classes = [IsListener]

    def post(self, request, track_id):
        """Проверяет доступ и возвращает свежую ссылку на трек."""
        track_access = get_object_or_404(
            ListenerTrackAccess.objects.select_related(
                'track',
                'track__album',
                'track__album__owner',
                'track__album__owner__artist_profile',
            ),
            user=request.user,
            track_id=track_id,
        )
        track = track_access.track

        if not track.audio_file:
            return Response(
                {'detail': 'Файл трека временно недоступен.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        filename = DownloadFilenameService.get_track_filename(track)

        try:
            link = DownloadLinkService.get_link(
                field_file=track.audio_file,
                filename=filename,
            )
        except FileNotFoundError:
            return Response(
                {'detail': 'Файл трека временно недоступен.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DownloadLinkSerializer(
            link,
            context={'request': request},
        )
        return Response(serializer.data)


@archive_download_link_schema
class PurchasedMusicArchiveDownloadLinkView(APIView):
    """Выдаёт временную ссылку на готовый архив полностью доступного релиза."""

    permission_classes = [IsListener]

    def post(self, request, album_id):
        """Проверяет полный доступ и возвращает свежую ссылку на ZIP."""
        album_access = get_object_or_404(
            ListenerAlbumAccess.objects.select_related(
                'album',
                'album__owner',
                'album__owner__artist_profile',
            ),
            user=request.user,
            album_id=album_id,
            is_fully_available=True,
        )
        album = album_access.album

        AlbumArchiveScheduler.schedule(album)

        archive = (
            AlbumArchive.objects
            .filter(album_id=album.id)
            .only('file', 'status')
            .first()
        )

        if archive is None or archive.status != AlbumArchive.Status.READY:
            archive_status = (
                archive.status
                if archive is not None
                else AlbumArchive.Status.PENDING
            )

            return Response(
                {
                    'detail': 'Архив ещё не готов.',
                    'status': archive_status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if not archive.file:
            return Response(
                {'detail': 'Файл архива временно недоступен.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        filename = DownloadFilenameService.get_archive_filename(album)

        try:
            link = DownloadLinkService.get_link(
                field_file=archive.file,
                filename=filename,
            )
        except FileNotFoundError:
            return Response(
                {'detail': 'Файл архива временно недоступен.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DownloadLinkSerializer(
            link,
            context={'request': request},
        )
        return Response(serializer.data)
