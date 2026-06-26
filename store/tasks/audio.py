"""Celery-задачи обработки аудио."""

from celery import shared_task

from store.services.audio.preparation import (
    TrackAudioPreparationService,
)


@shared_task(
    queue='media',
    ignore_result=True,
)
def prepare_track_audio(track_id: int) -> None:
    """Подготавливает preview и stream указанного трека."""
    TrackAudioPreparationService.prepare(track_id)
