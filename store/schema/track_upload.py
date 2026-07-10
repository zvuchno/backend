"""Схемы API прямой загрузки оригинальных файлов треков."""

from drf_spectacular.utils import OpenApiResponse, extend_schema

from store.serializers import (
    TrackUploadInitiateSerializer,
    TrackUploadLocalFileResponseSerializer,
    TrackUploadResponseSerializer,
)

TRACK_UPLOAD_TAGS = ('Tracks',)

track_upload_initiate_schema = extend_schema(
    summary='Инициализировать загрузку трека',
    description=(
        'Создаёт черновой трек в альбоме, создаёт попытку загрузки '
        'и возвращает transport-инструкцию для передачи файла '
        'во временное хранилище.'
    ),
    request=TrackUploadInitiateSerializer,
    responses={
        201: TrackUploadResponseSerializer,
        400: OpenApiResponse(description='Ошибка валидации файла.'),
        403: OpenApiResponse(description='Нет доступа к альбому.'),
        404: OpenApiResponse(description='Альбом не найден.'),
        503: OpenApiResponse(
            description='Не настроен транспорт загрузки.',
        ),
    },
    tags=TRACK_UPLOAD_TAGS,
)

track_upload_receive_file_schema = extend_schema(
    summary='Передать файл в локальное staging-хранилище',
    description=(
        'Локальный dev-endpoint для загрузки файла через Django, '
        'когда Object Storage отключён. В production при USE_S3_MEDIA=True '
        'этот endpoint недоступен.'
    ),
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'file': {
                    'type': 'string',
                    'format': 'binary',
                },
            },
            'required': ['file'],
        },
    },
    responses={
        200: TrackUploadLocalFileResponseSerializer,
        400: OpenApiResponse(description='Файл не передан или невалиден.'),
        403: OpenApiResponse(description='Нет доступа к загрузке.'),
        404: OpenApiResponse(
            description='Загрузка не найдена или endpoint отключен.',
        ),
    },
    tags=TRACK_UPLOAD_TAGS,
)

track_upload_complete_schema = extend_schema(
    summary='Завершить загрузку трека',
    description=(
        'Проверяет staging-файл, переносит его в постоянное хранилище, '
        'назначает audio_file и position треку, помечает загрузку '
        'завершённой и запускает подготовку audio preview/stream.'
    ),
    request=None,
    responses={
        200: TrackUploadResponseSerializer,
        400: OpenApiResponse(
            description='Staging-файл не найден или не прошёл проверку.',
        ),
        403: OpenApiResponse(description='Нет доступа к загрузке.'),
        404: OpenApiResponse(description='Загрузка не найдена.'),
    },
    tags=TRACK_UPLOAD_TAGS,
)
