"""Celery-задачи обработки аудио."""

from celery import shared_task

from store.exceptions import TemporaryAudioStorageError
from store.services.audio.preparation import (
    TrackAudioPreparationService,
)


@shared_task(
    queue='media',
    bind=True,
    ignore_result=True,
    max_retries=3,
    default_retry_delay=120,
)
def prepare_track_audio(self, track_id: int) -> None:
    """Подготавливает preview и stream указанного трека."""
    try:
        TrackAudioPreparationService.prepare(track_id)
    except TemporaryAudioStorageError as error:
        raise self.retry(exc=error)
