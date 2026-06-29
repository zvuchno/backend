"""API плеера для публичного preview и будущего stream."""

import logging

from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import Album, Track, TrackGeneratedAudio
from store.schema import (
    player_album_schema,
    player_track_play_schema,
)
from store.serializers import PlayerAlbumSerializer
from store.views.mixins import TrackReadQuerysetMixin

logger = logging.getLogger(__name__)


@player_album_schema
class PlayerAlbumView(TrackReadQuerysetMixin, GenericAPIView):
    """Возвращает данные альбома для очереди плеера."""

    serializer_class = PlayerAlbumSerializer
    permission_classes = (AllowAny,)
    lookup_url_kwarg = 'album_id'

    def get_queryset(self):
        """Возвращает альбом с доступными треками для плеера."""
        tracks_queryset = (
            self
            .get_track_read_queryset(
                action='retrieve',
            )
            .select_related('generated')
            .order_by('position', 'id')
        )

        return (
            Album.objects
            .visible_for(
                self.request.user,
                action='retrieve',
            )
            .select_related(
                'owner__artist_profile',
            )
            .prefetch_related(
                Prefetch(
                    'tracks',
                    queryset=tracks_queryset,
                ),
            )
        )

    def get(self, request, *args, **kwargs):
        """Возвращает альбом и очередь его треков."""
        album = self.get_object()

        return Response(
            self.get_serializer(album).data,
        )


@player_track_play_schema
class PlayerTrackPlayView(APIView):
    """Перенаправляет на доступный источник воспроизведения трека."""

    permission_classes = (AllowAny,)

    def get(self, request, track_id: int):
        """Перенаправляет на preview, если оно готово."""
        track = (
            Track.objects
            .visible_for(request.user, action='retrieve')
            .select_related(
                'generated',
            )
            .filter(pk=track_id)
            .first()
        )

        if track is None:
            raise Http404

        generated = getattr(track, 'generated', None)

        if generated is None:
            return Response(
                {
                    'detail': 'Превью трека ещё готовится.',
                    'status': TrackGeneratedAudio.ProcessingStatus.PENDING,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if generated.preview_status in (
            TrackGeneratedAudio.ProcessingStatus.PENDING,
            TrackGeneratedAudio.ProcessingStatus.BUILDING,
        ):
            return Response(
                {
                    'detail': 'Превью трека ещё готовится.',
                    'status': generated.preview_status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if (
            generated.preview_status
            == TrackGeneratedAudio.ProcessingStatus.FAILED
        ):
            return Response(
                {
                    'detail': 'Не удалось подготовить превью трека.',
                    'status': generated.preview_status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if not generated.preview_file or not generated.preview_duration:
            return self._preview_unavailable_response(
                code='preview_file_missing',
            )

        preview_file = generated.preview_file

        try:
            if not preview_file.storage.exists(preview_file.name):
                logger.warning(
                    'Preview file is missing in storage: '
                    'track_id=%s generated_audio_id=%s file_name=%s',
                    track.pk,
                    generated.pk,
                    preview_file.name,
                )
                return self._preview_unavailable_response(
                    code='preview_file_not_found',
                )

            preview_url = preview_file.url
        except Exception:
            logger.exception(
                'Could not access preview file in storage: '
                'track_id=%s generated_audio_id=%s file_name=%s',
                track.pk,
                generated.pk,
                preview_file.name,
            )
            return self._preview_unavailable_response(
                code='preview_storage_unavailable',
            )

        return redirect(preview_url)

    @staticmethod
    def _preview_unavailable_response(code: str) -> Response:
        """Возвращает ошибку недоступного preview."""
        return Response(
            {
                'detail': 'Превью трека временно недоступно.',
                'code': code,
            },
            status=status.HTTP_404_NOT_FOUND,
        )
