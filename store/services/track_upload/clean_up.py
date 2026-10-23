"""Очистка заброшенных загрузок оригинальных файлов треков."""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .upload_storage import TrackUploadStorageService
from store.models import TrackUpload

logger = logging.getLogger(__name__)

TRACK_UPLOAD_CLEANUP_DELAY = timedelta(days=1)


class TrackUploadCleanupService:
    """Удаляет данные заброшенных прямых загрузок треков."""

    @classmethod
    def cleanup_expired(cls) -> dict[str, int]:
        """Удаляет просроченные upload attempts и их staging-файлы."""
        cleanup_before = timezone.now() - TRACK_UPLOAD_CLEANUP_DELAY

        upload_ids = list(
            TrackUpload.objects
            .filter(
                completed_at__isnull=True,
                expires_at__lt=cleanup_before,
            )
            .exclude(
                status=TrackUpload.Status.COMPLETED,
            )
            .values_list('pk', flat=True),
        )

        result = {
            'deleted': 0,
            'skipped': 0,
            'storage_errors': 0,
        }

        for upload_id in upload_ids:
            cleanup_result = cls._cleanup_one(
                upload_id=upload_id,
                cleanup_before=cleanup_before,
            )
            result[cleanup_result] += 1

        return result

    @classmethod
    def _cleanup_one(
        cls,
        *,
        upload_id: int,
        cleanup_before,
    ) -> str:
        """Удаляет один заброшенный upload или пропускает изменившийся."""
        with transaction.atomic():
            try:
                upload = (
                    TrackUpload.objects
                    .select_for_update()
                    .select_related('track')
                    .get(pk=upload_id)
                )
            except TrackUpload.DoesNotExist:
                return 'skipped'

            if (
                upload.status == TrackUpload.Status.COMPLETED
                or upload.completed_at is not None
                or upload.expires_at >= cleanup_before
            ):
                return 'skipped'

            try:
                TrackUploadStorageService.delete_staging(
                    upload=upload,
                )
            except Exception:
                logger.exception(
                    'Не удалось удалить staging-файл '
                    'заброшенной загрузки трека. upload_id=%s',
                    upload.pk,
                )
                return 'storage_errors'

            recording = upload.track
            recording_id = recording.pk

            if (
                upload.purpose == TrackUpload.Purpose.CREATE
                and not recording.audio_file
            ):
                recording.release_tracks.all().delete()
                recording.delete()
            else:
                upload.delete()

        logger.info(
            'Удалена заброшенная загрузка трека. '
            'upload_id=%s, recording_id=%s',
            upload_id,
            recording_id,
        )

        return 'deleted'
