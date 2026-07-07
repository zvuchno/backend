import logging

from celery import shared_task

from store.services.track_upload import TrackUploadCleanupService

logger = logging.getLogger(__name__)


@shared_task(queue='celery')
def cleanup_expired_track_uploads() -> dict[str, int]:
    """Удаляет заброшенные технические треки и staging-файлы."""
    result = TrackUploadCleanupService.cleanup_expired()

    logger.info(
        'Очистка заброшенных загрузок треков завершена. '
        'deleted=%s, skipped=%s, storage_errors=%s',
        result['deleted'],
        result['skipped'],
        result['storage_errors'],
    )

    return result
