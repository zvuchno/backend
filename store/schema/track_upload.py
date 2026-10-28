"""Схемы API прямой загрузки оригиналов мастер-записей."""

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)

from store.serializers import (
    TrackReplacementUploadInitiateSerializer,
    TrackUploadInitiateSerializer,
    TrackUploadLocalFileResponseSerializer,
    TrackUploadResponseSerializer,
)

TRACK_UPLOAD_TAGS = ('Tracks',)

track_upload_initiate_schema = extend_schema(
    summary='Инициализировать загрузку новой мастер-записи',
    description=(
        'Создаёт мастер-запись Recording для указанного артиста '
        'и попытку загрузки её оригинального аудиофайла. '
        'Пользователь должен иметь права на управление артистом. '
        'Размещение в релизе (ReleaseTrack) и товар не создаются. '
        'Клиент должен отправить файл по адресу upload.transport.url, '
        'передав поля из upload.transport.fields и сам файл в поле '
        'upload.transport.file_field_name. '
        'После успешной отправки необходимо вызвать upload.complete_url. '
        'Завершённую мастер-запись можно отдельно добавить в релиз.'
    ),
    request=TrackUploadInitiateSerializer,
    responses={
        201: TrackUploadResponseSerializer,
        400: OpenApiResponse(
            description='Некорректные параметры записи или файла.',
        ),
        403: OpenApiResponse(
            description='Нет прав на управление указанным артистом.',
        ),
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
    summary='Завершить загрузку оригинала мастер-записи',
    description=(
        'Завершает прямую загрузку после того, '
        'как клиент успешно отправил файл '
        'по transport-инструкции. Проверяет staging-файл, '
        'переносит его в постоянное хранилище мастер-записи, '
        'помечает загрузку завершённой и запускает подготовку '
        'audio preview/stream.'
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


track_upload_replace_initiate_schema = extend_schema(
    summary='Инициализировать замену оригинала записи',
    description=(
        'Создаёт попытку загрузки нового оригинального аудиофайла '
        'для существующей мастер-записи. '
        'Необходимо передать track_id или recording_id. '
        'Если указаны оба идентификатора, они должны относиться '
        'к одной Recording. '
        'После отправки файла по инструкции upload.transport '
        'необходимо вызвать upload.complete_url. '
        'Замена оригинала не изменяет размещения в релизах '
        'и их коммерческие параметры.'
    ),
    request=TrackReplacementUploadInitiateSerializer,
    responses={
        201: TrackUploadResponseSerializer,
        400: OpenApiResponse(
            description='Некорректные идентификаторы или параметры файла.',
        ),
        403: OpenApiResponse(
            description='Нет прав на мастер-запись.',
        ),
        503: OpenApiResponse(
            description='Не настроен транспорт загрузки.',
        ),
    },
    tags=TRACK_UPLOAD_TAGS,
)
