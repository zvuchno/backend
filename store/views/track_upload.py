from http import HTTPStatus

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsArtist

from store.constants import ZERO_MONEY
from store.models import Album, Track, TrackUpload
from store.schema import (
    track_file_upload_initiate_schema,
    track_upload_complete_schema,
    track_upload_initiate_schema,
    track_upload_receive_file_schema,
)
from store.serializers import (
    TrackUploadFileInitiateSerializer,
    TrackUploadInitiateSerializer,
    TrackUploadResponseSerializer,
)
from store.services.track_upload import (
    TrackUploadService,
    TrackUploadStorageError,
    TrackUploadStorageService,
    TrackUploadTransportService,
    UploadTransportConfigurationError,
)


def _check_album_owner(*, request, album: Album) -> None:
    """Проверяет, что текущий артист владеет альбомом."""
    if album.owner_id != request.user.id:
        raise PermissionDenied(
            'Нельзя загружать треки в чужой альбом.',
        )


def _check_upload_owner(*, request, upload: TrackUpload) -> None:
    """Проверяет, что текущий артист владеет альбомом загрузки."""
    if upload.track.album.owner_id != request.user.id:
        raise PermissionDenied(
            'Нельзя управлять чужой загрузкой трека.',
        )


def _check_track_upload_access(*, request, track: Track) -> None:
    """Проверяет, что пользователь может управлять загрузкой файла трека."""
    if track.album.owner_id != request.user.id:
        raise PermissionDenied(
            'Нельзя управлять загрузкой файла чужого трека.',
        )


def _build_track_upload_response(
    *,
    request,
    upload: TrackUpload,
    transport=None,
) -> dict:
    """Формирует ответ API по попытке загрузки трека."""
    track = upload.track
    product = getattr(track, 'product', None)

    data = {
        'track': {
            'id': track.pk,
            'name': track.name,
            'description': track.description,
            'position': track.position,
            'price': product.price if product else ZERO_MONEY,
            'allow_overpay': product.allow_overpay if product else False,
        },
        'upload': {
            'id': upload.pk,
            'status': upload.status,
            'uploaded_size': upload.uploaded_size,
            'expires_at': upload.expires_at,
            'completed_at': upload.completed_at,
            'complete_url': request.build_absolute_uri(
                reverse(
                    'api:store:track-upload-complete',
                    args=(upload.pk,),
                ),
            ),
        },
    }

    if transport is not None:
        data['upload']['transport'] = {
            'method': transport.method,
            'url': transport.url,
            'headers': transport.headers,
            'fields': transport.fields,
            'file_field_name': transport.file_field_name,
        }

    return data


class AlbumTrackUploadInitiateView(APIView):
    """Создаёт черновой трек и возвращает инструкцию загрузки."""

    permission_classes = (IsArtist,)

    @track_upload_initiate_schema
    def post(self, request, album_id):
        """Инициализирует прямую загрузку оригинального файла трека."""
        album = get_object_or_404(Album, pk=album_id)
        _check_album_owner(request=request, album=album)

        serializer = TrackUploadInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            track, upload = TrackUploadService.create_pending_track(
                album=album,
                filename=serializer.validated_data['filename'],
                size=serializer.validated_data['size'],
                content_type=serializer.validated_data['content_type'],
                name=serializer.validated_data['name'],
                description=serializer.validated_data['description'],
                price=serializer.validated_data['price'],
                allow_overpay=serializer.validated_data['allow_overpay'],
            )

            local_upload_url = request.build_absolute_uri(
                reverse(
                    'api:store:track-upload-receive-file',
                    args=(upload.pk,),
                ),
            )

            upload_instruction = (
                TrackUploadTransportService.create_instruction(
                    upload=upload,
                    local_upload_url=local_upload_url,
                )
            )
        except ValidationError as exc:
            return Response(
                {
                    'detail': exc.messages,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
        except UploadTransportConfigurationError as exc:
            return Response(
                {
                    'detail': str(exc),
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )

        upload.track = track

        return Response(
            TrackUploadResponseSerializer(
                instance=_build_track_upload_response(
                    request=request,
                    upload=upload,
                    transport=upload_instruction,
                ),
            ).data,
            status=HTTPStatus.CREATED,
        )


class TrackUploadReceiveFileView(APIView):
    """Принимает файл в локальном режиме без Object Storage."""

    permission_classes = (IsArtist,)
    parser_classes = (MultiPartParser,)

    @track_upload_receive_file_schema
    def post(self, request, upload_id):
        """Сохраняет файл во временное локальное хранилище."""
        if settings.USE_S3_MEDIA:
            raise Http404

        upload = get_object_or_404(
            TrackUpload.objects.select_related('track__album'),
            pk=upload_id,
        )
        _check_upload_owner(request=request, upload=upload)

        uploaded_file = request.FILES.get('file')

        if uploaded_file is None:
            return Response(
                {
                    'detail': 'Не передан файл.',
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        try:
            upload = TrackUploadService.receive_local_file(
                upload=upload,
                uploaded_file=uploaded_file,
            )
        except ValidationError as exc:
            return Response(
                {
                    'detail': exc.messages,
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        return Response(
            {
                'upload': {
                    'id': upload.pk,
                    'status': upload.status,
                    'uploaded_size': upload.uploaded_size,
                },
            },
        )


class TrackUploadCompleteView(APIView):
    """Подтверждает staging-файл и финализирует трек."""

    permission_classes = (IsArtist,)

    @track_upload_complete_schema
    def post(self, request, upload_id):
        """Переносит staging-файл в постоянное хранилище."""
        upload = get_object_or_404(
            TrackUpload.objects.select_related('track__album'),
            pk=upload_id,
        )
        _check_upload_owner(request=request, upload=upload)

        try:
            upload = TrackUploadStorageService.complete(upload=upload)
        except TrackUploadStorageError as exc:
            return Response(
                {
                    'detail': str(exc),
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        return Response(
            TrackUploadResponseSerializer(
                instance=_build_track_upload_response(
                    request=request,
                    upload=upload,
                ),
            ).data,
        )


class TrackFileUploadInitiateView(APIView):
    """Создаёт попытку замены оригинального файла трека."""

    permission_classes = (IsArtist,)

    @track_file_upload_initiate_schema
    def post(self, request, track_id):
        """Инициализирует прямую замену оригинального файла трека."""
        track = get_object_or_404(
            Track.objects.select_related('album'),
            pk=track_id,
        )
        _check_track_upload_access(request=request, track=track)

        serializer = TrackUploadFileInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            upload = TrackUploadService.create_replacement_upload(
                track=track,
                filename=serializer.validated_data['filename'],
                size=serializer.validated_data['size'],
                content_type=serializer.validated_data['content_type'],
            )

            local_upload_url = request.build_absolute_uri(
                reverse(
                    'api:store:track-upload-receive-file',
                    args=(upload.pk,),
                ),
            )

            upload_instruction = (
                TrackUploadTransportService.create_instruction(
                    upload=upload,
                    local_upload_url=local_upload_url,
                )
            )
        except ValidationError as exc:
            return Response(
                {
                    'detail': exc.messages,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
        except UploadTransportConfigurationError as exc:
            return Response(
                {
                    'detail': str(exc),
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )

        return Response(
            TrackUploadResponseSerializer(
                instance=_build_track_upload_response(
                    request=request,
                    upload=upload,
                    transport=upload_instruction,
                ),
            ).data,
            status=HTTPStatus.CREATED,
        )
