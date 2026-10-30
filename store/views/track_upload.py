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

from common.access import can_manage_artist
from common.permissions import CanCreateArtistContent

from store.models import Recording, TrackUpload
from store.schema import (
    track_upload_complete_schema,
    track_upload_initiate_schema,
    track_upload_receive_file_schema,
    track_upload_replace_initiate_schema,
)
from store.serializers import (
    TrackReplacementUploadInitiateSerializer,
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


def _check_upload_access(*, request, upload: TrackUpload) -> None:
    """Проверяет право управлять загрузкой записи."""
    if not can_manage_artist(
        request.user,
        upload.track.owner,
    ):
        raise PermissionDenied(
            'Нельзя управлять чужой загрузкой трека.',
        )


def _build_track_upload_response(
    *,
    request,
    recording: Recording,
    upload: TrackUpload,
    transport=None,
) -> dict:
    """Формирует ответ API по попытке загрузки мастер-записи."""
    complete_path = reverse(
        'api:store:track-upload-complete',
        args=(upload.pk,),
    )

    data = {
        'recording': {
            'id': recording.pk,
            'name': recording.name,
            'description': recording.description,
            'isrc': recording.isrc,
        },
        'upload': {
            'id': upload.pk,
            'status': upload.status,
            'uploaded_size': upload.uploaded_size,
            'expires_at': upload.expires_at,
            'completed_at': upload.completed_at,
            'complete_url': request.build_absolute_uri(
                complete_path,
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


class TrackUploadInitiateView(APIView):
    """Создаёт мастер-запись и возвращает инструкцию загрузки."""

    permission_classes = (CanCreateArtistContent,)

    @track_upload_initiate_schema
    def post(self, request):
        """Инициализирует загрузку оригинала новой записи."""
        serializer = TrackUploadInitiateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        owner = data['owner']

        if not can_manage_artist(request.user, owner):
            raise PermissionDenied(
                'Нельзя создавать записи для чужого артиста.',
            )

        try:
            recording, upload = TrackUploadService.create_recording_upload(
                owner=owner,
                created_by=request.user,
                filename=data['filename'],
                size=data['size'],
                content_type=data['content_type'],
                name=data['name'],
                description=data['description'],
                isrc=data.get('isrc'),
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
                {'detail': exc.messages},
                status=HTTPStatus.BAD_REQUEST,
            )

        except UploadTransportConfigurationError as exc:
            return Response(
                {'detail': str(exc)},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )

        return Response(
            TrackUploadResponseSerializer(
                instance=_build_track_upload_response(
                    request=request,
                    recording=recording,
                    upload=upload,
                    transport=upload_instruction,
                ),
            ).data,
            status=HTTPStatus.CREATED,
        )


class TrackUploadReceiveFileView(APIView):
    """Принимает файл в локальном режиме без Object Storage."""

    permission_classes = (CanCreateArtistContent,)
    parser_classes = (MultiPartParser,)

    @track_upload_receive_file_schema
    def post(self, request, upload_id):
        """Сохраняет файл во временное локальное хранилище."""
        if settings.USE_S3_MEDIA:
            raise Http404

        upload = get_object_or_404(
            TrackUpload.objects.select_related(
                'track__owner__label',
            ),
            pk=upload_id,
        )
        _check_upload_access(request=request, upload=upload)

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

    permission_classes = (CanCreateArtistContent,)

    @track_upload_complete_schema
    def post(self, request, upload_id):
        """Финализирует оригинальный файл мастер-записи."""
        upload = get_object_or_404(
            TrackUpload.objects.select_related(
                'track__owner__label',
            ),
            pk=upload_id,
        )

        _check_upload_access(
            request=request,
            upload=upload,
        )

        try:
            upload = TrackUploadStorageService.complete(
                upload=upload,
            )
        except TrackUploadStorageError as exc:
            return Response(
                {'detail': str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )

        return Response(
            TrackUploadResponseSerializer(
                instance=_build_track_upload_response(
                    request=request,
                    recording=upload.track,
                    upload=upload,
                ),
            ).data,
        )


class TrackReplacementUploadInitiateView(APIView):
    """Создаёт попытку замены оригинала мастер-записи."""

    permission_classes = (CanCreateArtistContent,)

    @track_upload_replace_initiate_schema
    def post(self, request):
        """Инициализирует прямую замену оригинального файла."""
        serializer = TrackReplacementUploadInitiateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        recording = data['recording']

        if not can_manage_artist(
            request.user,
            recording.owner,
        ):
            raise PermissionDenied(
                'Нельзя заменять оригинал чужой записи.',
            )

        try:
            upload = TrackUploadService.create_replacement_upload(
                recording=recording,
                filename=data['filename'],
                size=data['size'],
                content_type=data['content_type'],
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
                {'detail': exc.messages},
                status=HTTPStatus.BAD_REQUEST,
            )

        except UploadTransportConfigurationError as exc:
            return Response(
                {'detail': str(exc)},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )

        return Response(
            TrackUploadResponseSerializer(
                instance=_build_track_upload_response(
                    request=request,
                    recording=recording,
                    upload=upload,
                    transport=upload_instruction,
                ),
            ).data,
            status=HTTPStatus.CREATED,
        )
