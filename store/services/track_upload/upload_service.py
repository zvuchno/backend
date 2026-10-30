"""Сервис прямой загрузки оригинальных файлов треков."""

from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_AUDIOFILE_SIZE_MB,
)
from store.models import Recording, TrackUpload
from store.upload_paths import track_upload_staging_key
from store.validators import validate_isrc_format

TRACK_UPLOAD_TTL = timedelta(hours=1)


class TrackUploadService:
    """Управляет созданием треков и попытками загрузки оригиналов."""

    @classmethod
    @transaction.atomic
    def create_replacement_upload(
        cls,
        *,
        recording: Recording,
        filename: str,
        size: int,
        content_type: str = '',
    ) -> TrackUpload:
        """Создаёт попытку замены оригинала мастер-записи."""
        filename = Path(filename).name

        cls._validate_file_metadata(
            filename=filename,
            size=size,
        )

        recording = Recording.objects.select_for_update().get(pk=recording.pk)

        return TrackUpload.objects.create(
            track=recording,
            purpose=TrackUpload.Purpose.REPLACE,
            staging_key=track_upload_staging_key(
                recording.pk,
                filename,
            ),
            original_filename=filename,
            expected_size=size,
            content_type=content_type,
            expires_at=timezone.now() + TRACK_UPLOAD_TTL,
        )

    @classmethod
    @transaction.atomic
    def create_recording_upload(
        cls,
        *,
        owner,
        created_by,
        filename: str,
        size: int,
        content_type: str = '',
        name: str = '',
        description: str = '',
        isrc: str | None = None,
    ) -> tuple[Recording, TrackUpload]:
        """Создаёт мастер-запись и попытку загрузки оригинала."""
        filename = Path(filename).name

        cls._validate_file_metadata(
            filename=filename,
            size=size,
        )

        isrc = isrc or None
        if isrc is not None:
            validate_isrc_format(isrc)

        recording = Recording.objects.create(
            owner=owner,
            created_by=created_by,
            name=name.strip() or cls._get_track_name(filename),
            description=description or '',
            isrc=isrc,
        )

        upload = TrackUpload.objects.create(
            track=recording,
            purpose=TrackUpload.Purpose.CREATE,
            staging_key=track_upload_staging_key(
                recording.pk,
                filename,
            ),
            original_filename=filename,
            expected_size=size,
            content_type=content_type,
            expires_at=timezone.now() + TRACK_UPLOAD_TTL,
        )

        return recording, upload

    @classmethod
    @transaction.atomic
    def receive_local_file(
        cls,
        *,
        upload: TrackUpload,
        uploaded_file: UploadedFile,
    ) -> TrackUpload:
        """Сохраняет файл локальной загрузки во временное хранилище."""
        upload = (
            TrackUpload.objects
            .select_for_update()
            .select_related('track')
            .get(pk=upload.pk)
        )

        if upload.status != TrackUpload.Status.INITIATED:
            raise ValidationError(
                'Эта попытка загрузки больше не ожидает файл.',
            )

        if timezone.now() >= upload.expires_at:
            upload.status = TrackUpload.Status.EXPIRED
            upload.error = 'Срок действия инструкции загрузки истёк.'
            upload.save(
                update_fields=(
                    'status',
                    'error',
                    'updated_at',
                ),
            )
            raise ValidationError(
                'Срок действия инструкции загрузки истёк.',
            )

        filename = Path(uploaded_file.name).name

        if filename != upload.original_filename:
            raise ValidationError(
                'Имя переданного файла не совпадает '
                'с файлом попытки загрузки.',
            )

        cls._validate_file_metadata(
            filename=filename,
            size=uploaded_file.size,
        )

        if uploaded_file.size != upload.expected_size:
            raise ValidationError(
                'Фактический размер файла не совпадает с заявленным.',
            )

        storage = upload.track.audio_file.storage

        storage.delete(upload.staging_key)
        saved_name = storage.save(
            upload.staging_key,
            uploaded_file,
        )

        if saved_name != upload.staging_key:
            storage.delete(saved_name)
            raise ValidationError(
                'Не удалось сохранить файл по ожидаемому временному пути.',
            )

        upload.status = TrackUpload.Status.UPLOADED
        upload.uploaded_size = uploaded_file.size
        upload.save(
            update_fields=(
                'status',
                'uploaded_size',
                'updated_at',
            ),
        )

        return upload

    @staticmethod
    def _validate_file_metadata(*, filename: str, size: int) -> None:
        """Проверяет метаданные файла до создания попытки загрузки."""
        extension = Path(filename).suffix.lower().lstrip('.')
        max_size = MAX_AUDIOFILE_SIZE_MB * 1024 * 1024

        if not filename:
            raise ValidationError('Не указано имя аудиофайла.')

        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise ValidationError(
                'Поддерживаются только файлы MP3, WAV и FLAC.',
            )

        if size <= 0:
            raise ValidationError(
                'Размер аудиофайла должен быть больше нуля.',
            )

        if size > max_size:
            raise ValidationError(
                f'Размер аудиофайла не должен превышать '
                f'{MAX_AUDIOFILE_SIZE_MB} МБ.',
            )

    @staticmethod
    def _get_track_name(filename: str) -> str:
        """Возвращает предварительное название трека из имени файла."""
        return Path(filename).stem
