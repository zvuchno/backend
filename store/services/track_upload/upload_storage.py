"""Завершение загрузки оригинальных файлов треков."""

import logging
from pathlib import Path
from shutil import copyfile

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from store.models import Album, Track, TrackUpload
from store.services.album_archive import AlbumArchiveScheduler
from store.services.audio import TrackGeneratedAudioScheduler
from store.upload_paths import track_audio_upload_to

logger = logging.getLogger(__name__)


class TrackUploadStorageError(RuntimeError):
    """Возникает, когда staging-файл нельзя подтвердить или перенести."""


class TrackUploadStorageService:
    """Завершает загрузку файла из staging в постоянное хранилище."""

    @classmethod
    @transaction.atomic
    def complete(cls, *, upload: TrackUpload) -> TrackUpload:
        """Завершает загрузку файла.

        Подтверждает файл,
        переносит его в Track.audio_file и запускает обработку.
        """
        upload = (
            TrackUpload.objects
            .select_for_update()
            .select_related('track')
            .get(pk=upload.pk)
        )

        if upload.status == TrackUpload.Status.COMPLETED:
            return upload

        if upload.status not in {
            TrackUpload.Status.INITIATED,
            TrackUpload.Status.UPLOADED,
        }:
            raise TrackUploadStorageError(
                'Эту попытку загрузки нельзя завершить.',
            )

        final_key = track_audio_upload_to(
            upload.track,
            upload.original_filename,
        )

        if settings.USE_S3_MEDIA:
            uploaded_size = cls._copy_s3_staging_to_final(
                upload=upload,
                final_key=final_key,
            )
        else:
            uploaded_size = cls._copy_local_staging_to_final(
                upload=upload,
                final_key=final_key,
            )

        if uploaded_size != upload.expected_size:
            raise TrackUploadStorageError(
                'Размер staging-файла не совпадает с ожидаемым.',
            )

        track = upload.track

        if upload.purpose == TrackUpload.Purpose.REPLACE:
            cls._replace_track_audio(
                track=track,
                final_key=final_key,
            )
        else:
            cls._finalize_new_track(
                track=track,
                final_key=final_key,
            )

        upload.status = TrackUpload.Status.COMPLETED
        upload.uploaded_size = uploaded_size
        upload.completed_at = timezone.now()
        upload.error = ''
        upload.save(
            update_fields=(
                'status',
                'uploaded_size',
                'completed_at',
                'error',
                'updated_at',
            ),
        )

        TrackGeneratedAudioScheduler.schedule(track)
        AlbumArchiveScheduler.schedule(track.album)

        transaction.on_commit(
            lambda upload=upload: cls._delete_staging_safely(
                upload=upload,
            ),
        )

        return upload

    @classmethod
    def _finalize_new_track(
        cls,
        *,
        track: Track,
        final_key: str,
    ) -> None:
        """Финализирует новый трек после успешной загрузки файла."""
        album = Album.objects.select_for_update().get(
            pk=track.album_id,
        )

        last_position = (
            Track.objects
            .filter(
                album_id=album.pk,
                position__isnull=False,
            )
            .exclude(
                pk=track.pk,
                audio_file='',
            )
            .aggregate(
                max_position=Max('position'),
            )
        )['max_position']

        track.position = (last_position or 0) + 1
        track.audio_file.name = final_key
        track.save(
            update_fields=(
                'audio_file',
                'position',
                'updated_at',
            ),
        )

    @classmethod
    def _replace_track_audio(
        cls,
        *,
        track: Track,
        final_key: str,
    ) -> None:
        """Заменяет оригинальный файл существующего трека."""
        track.audio_file.name = final_key
        track.save(
            update_fields=(
                'audio_file',
                'updated_at',
            ),
        )

    @classmethod
    def _copy_local_staging_to_final(
        cls,
        *,
        upload: TrackUpload,
        final_key: str,
    ) -> int:
        """Копирует локальный staging-файл в постоянный путь."""
        storage = upload.track.audio_file.storage

        source_path = Path(storage.path(upload.staging_key))
        target_path = Path(storage.path(final_key))

        if not source_path.is_file():
            raise TrackUploadStorageError(
                'Временный файл загрузки не найден.',
            )

        uploaded_size = source_path.stat().st_size

        if uploaded_size != upload.expected_size:
            raise TrackUploadStorageError(
                'Размер временного файла не совпадает с ожидаемым.',
            )

        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        copyfile(source_path, target_path)

        return uploaded_size

    @classmethod
    def _copy_s3_staging_to_final(
        cls,
        *,
        upload: TrackUpload,
        final_key: str,
    ) -> int:
        """Копирует staging-объект Object Storage в постоянный путь."""
        client = cls._get_s3_client()
        bucket_name = settings.AWS_PRIVATE_STORAGE_BUCKET_NAME
        source_key = cls._get_bucket_key(upload.staging_key)
        target_key = cls._get_bucket_key(final_key)

        try:
            head = client.head_object(
                Bucket=bucket_name,
                Key=source_key,
            )
        except ClientError as exc:
            if cls._is_not_found_error(exc):
                raise TrackUploadStorageError(
                    'Временный файл загрузки не найден.',
                ) from exc

            raise TrackUploadStorageError(
                'Не удалось проверить временный файл загрузки.',
            ) from exc

        uploaded_size = head['ContentLength']

        if uploaded_size != upload.expected_size:
            raise TrackUploadStorageError(
                'Размер временного файла не совпадает с ожидаемым.',
            )

        try:
            client.copy_object(
                Bucket=bucket_name,
                Key=target_key,
                CopySource={
                    'Bucket': bucket_name,
                    'Key': source_key,
                },
            )
        except ClientError as exc:
            raise TrackUploadStorageError(
                'Не удалось перенести файл в постоянное хранилище.',
            ) from exc

        return uploaded_size

    @classmethod
    def delete_staging(cls, *, upload: TrackUpload) -> None:
        """Удаляет staging-файл загрузки из текущего хранилища."""
        if settings.USE_S3_MEDIA:
            cls._get_s3_client().delete_object(
                Bucket=settings.AWS_PRIVATE_STORAGE_BUCKET_NAME,
                Key=cls._get_bucket_key(upload.staging_key),
            )
            return

        upload.track.audio_file.storage.delete(upload.staging_key)

    @classmethod
    def _delete_staging_safely(cls, *, upload: TrackUpload) -> None:
        """Удаляет staging-файл после успешного завершения загрузки."""
        try:
            cls.delete_staging(upload=upload)
        except Exception:
            logger.exception(
                'Не удалось удалить staging-файл трека: %s',
                upload.staging_key,
            )

    @staticmethod
    def _is_not_found_error(error: ClientError) -> bool:
        """Проверяет, что ошибка S3 означает отсутствие объекта."""
        error_code = error.response.get('Error', {}).get('Code')

        return error_code in {
            '404',
            'NoSuchKey',
            'NotFound',
        }

    @staticmethod
    def _get_bucket_key(storage_key: str) -> str:
        """Добавляет location private storage к относительному ключу."""
        location = settings.MEDIA_LOCATION.strip('/')
        storage_key = storage_key.lstrip('/')

        if not location:
            return storage_key

        return f'{location}/{storage_key}'

    @staticmethod
    def _get_s3_client() -> BaseClient:
        """Создаёт S3-клиент для Object Storage."""
        return boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(
                s3={
                    'addressing_style': settings.AWS_S3_ADDRESSING_STYLE,
                },
            ),
        )
