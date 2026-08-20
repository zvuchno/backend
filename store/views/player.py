"""API плеера для публичного preview и будущего stream."""

import logging

from django.db.models import Exists, OuterRef, Prefetch, Subquery
from django.http import Http404
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import (
    Album,
    ListenerTrackAccess,
    ProductVariant,
    Track,
    TrackGeneratedAudio,
)
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
        favorite_variant_id_subquery = Subquery(
            ProductVariant.objects
            .filter(
                product__track_id=OuterRef('pk'),
                is_active=True,
            )
            .order_by('id')
            .values('pk')[:1],
        )
        purchase_variant_id_subquery = Subquery(
            ProductVariant.objects
            .filter(
                product__track_id=OuterRef('pk'),
                product__price__gt=0,
                is_active=True,
            )
            .order_by('id')
            .values('pk')[:1],
        )

        if self.request.user.is_authenticated:
            full_access_subquery = ListenerTrackAccess.objects.filter(
                user=self.request.user,
                track_id=OuterRef('pk'),
            )
        else:
            full_access_subquery = ListenerTrackAccess.objects.none()

        tracks_queryset = (
            self
            .get_track_read_queryset(
                action='retrieve',
            )
            .select_related('generated')
            .annotate(
                favorite_variant_id=favorite_variant_id_subquery,
                purchase_variant_id=purchase_variant_id_subquery,
                has_full_access=Exists(full_access_subquery),
            )
            .order_by('position', 'id')
        )

        return (
            Album.objects
            .visible_for(
                self.request.user,
                action='retrieve',
            )
            .select_related(
                'artist',
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
        """Перенаправляет на доступную версию трека."""
        track = (
            Track.objects
            .visible_for(request.user, action='retrieve')
            .select_related('generated')
            .filter(pk=track_id)
            .first()
        )

        if track is None:
            raise Http404

        has_full_access = (
            request.user.is_authenticated
            and ListenerTrackAccess.objects.filter(
                user=request.user,
                track_id=track.pk,
            ).exists()
        )

        generated = getattr(track, 'generated', None)

        if generated is None:
            detail = (
                'Трек ещё готовится.'
                if has_full_access
                else 'Превью трека ещё готовится.'
            )

            return Response(
                {
                    'detail': detail,
                    'status': TrackGeneratedAudio.ProcessingStatus.PENDING,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if has_full_access:
            return self._redirect_to_stream(track, generated)

        return self._redirect_to_preview(track, generated)

    def _redirect_to_audio(
        self,
        track: Track,
        generated: TrackGeneratedAudio,
        audio_file,
        audio_status: str,
        pending_detail: str,
        failed_detail: str,
        unavailable_detail: str,
        code_prefix: str,
        audio_duration: int | None = None,
        require_duration: bool = False,
    ) -> Response:
        """Редиректит на подготовленный аудиофайл."""
        if audio_status in (
            TrackGeneratedAudio.ProcessingStatus.PENDING,
            TrackGeneratedAudio.ProcessingStatus.BUILDING,
        ):
            return Response(
                {
                    'detail': pending_detail,
                    'status': audio_status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if audio_status == TrackGeneratedAudio.ProcessingStatus.FAILED:
            return Response(
                {
                    'detail': failed_detail,
                    'status': audio_status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if not audio_file:
            return self._audio_unavailable_response(
                detail=unavailable_detail,
                code=f'{code_prefix}_file_missing',
            )

        if require_duration and not audio_duration:
            return self._audio_unavailable_response(
                detail=unavailable_detail,
                code=f'{code_prefix}_duration_missing',
            )

        try:
            if not audio_file.storage.exists(audio_file.name):
                logger.warning(
                    'Audio file is missing in storage: '
                    'track_id=%s generated_audio_id=%s '
                    'kind=%s file_name=%s',
                    track.pk,
                    generated.pk,
                    code_prefix,
                    audio_file.name,
                )
                return self._audio_unavailable_response(
                    detail=unavailable_detail,
                    code=f'{code_prefix}_file_not_found',
                )

            audio_url = audio_file.url
        except Exception:
            logger.exception(
                'Could not access audio file in storage: '
                'track_id=%s generated_audio_id=%s '
                'kind=%s file_name=%s',
                track.pk,
                generated.pk,
                code_prefix,
                audio_file.name,
            )
            return self._audio_unavailable_response(
                detail=unavailable_detail,
                code=f'{code_prefix}_storage_unavailable',
            )

        return redirect(audio_url)

    def _redirect_to_stream(
        self,
        track: Track,
        generated: TrackGeneratedAudio,
    ) -> Response:
        """Редиректит на полную версию трека."""
        return self._redirect_to_audio(
            track=track,
            generated=generated,
            audio_file=generated.stream_file,
            audio_status=generated.stream_status,
            pending_detail='Трек ещё готовится.',
            failed_detail='Не удалось подготовить трек.',
            unavailable_detail='Трек временно недоступен.',
            code_prefix='stream',
        )

    def _redirect_to_preview(
        self,
        track: Track,
        generated: TrackGeneratedAudio,
    ) -> Response:
        """Редиректит на превью."""
        return self._redirect_to_audio(
            track=track,
            generated=generated,
            audio_file=generated.preview_file,
            audio_status=generated.preview_status,
            pending_detail='Превью трека ещё готовится.',
            failed_detail='Не удалось подготовить превью трека.',
            unavailable_detail='Превью трека временно недоступно.',
            code_prefix='preview',
            audio_duration=generated.preview_duration,
            require_duration=True,
        )

    @staticmethod
    def _audio_unavailable_response(
        detail: str,
        code: str,
    ) -> Response:
        """Возвращает ошибку недоступного аудио."""
        return Response(
            {
                'detail': detail,
                'code': code,
            },
            status=status.HTTP_404_NOT_FOUND,
        )
