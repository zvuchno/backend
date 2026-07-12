"""Схемы API прямой загрузки оригинальных файлов треков."""

from drf_spectacular.utils import OpenApiResponse, extend_schema

from store.serializers import (
    TrackUploadFileInitiateSerializer,
    TrackUploadInitiateSerializer,
    TrackUploadLocalFileResponseSerializer,
    TrackUploadResponseSerializer,
)

TRACK_UPLOAD_TAGS = ('Tracks',)

track_upload_initiate_schema = extend_schema(
    summary='Инициализировать прямую загрузку трека в альбом',
    description=(
        'Создаёт черновой трек в указанном альбоме и возвращает инструкцию '
        'для загрузки оригинального аудиофайла. Клиент должен отправить файл '
        'по адресу upload.transport.url, '
        'передав все поля из upload.transport.fields '
        'и сам файл в поле upload.transport.file_field_name. После успешной '
        'отправки файла нужно вызвать upload.complete_url.'
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
        'Завершает прямую загрузку после того, '
        'как клиент успешно отправил файл '
        'по transport-инструкции. Проверяет staging-файл, '
        'переносит его в постоянное '
        'хранилище, назначает audio_file и position треку, помечает загрузку '
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


track_file_upload_initiate_schema = extend_schema(
    summary='Инициализировать замену файла трека',
    description=(
        'Создаёт попытку прямой загрузки нового оригинального аудиофайла '
        'для существующего трека и возвращает инструкцию для отправки файла. '
        'Клиент должен отправить файл по адресу upload.transport.url, '
        'передав все поля из upload.transport.fields и сам файл в поле '
        'upload.transport.file_field_name. После успешной отправки файла '
        'нужно вызвать upload.complete_url. При завершении загрузки '
        'сохраняются id трека, альбом, позиция и данные продажи.'
    ),
    request=TrackUploadFileInitiateSerializer,
    responses={
        201: TrackUploadResponseSerializer,
        400: OpenApiResponse(description='Ошибка валидации файла.'),
        403: OpenApiResponse(description='Нет доступа к треку.'),
        404: OpenApiResponse(description='Трек не найден.'),
        503: OpenApiResponse(
            description='Не настроен транспорт загрузки.',
        ),
    },
    tags=TRACK_UPLOAD_TAGS,
)
