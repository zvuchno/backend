"""Постановка задач подготовки аудио после commit."""

import logging

from django.db import transaction

from store.models import Recording

logger = logging.getLogger(__name__)


class TrackGeneratedAudioScheduler:
    """Ставит подготовку производных аудиофайлов в очередь."""

    @classmethod
    def schedule(cls, recording: Recording) -> None:
        """Ставит обработку записи в очередь после фиксации транзакции."""
        recording_id = recording.pk

        transaction.on_commit(
            lambda: cls._enqueue_safely(recording_id),
        )

    @staticmethod
    def _enqueue_safely(recording_id: int) -> None:
        """Ставит задачу в очередь, не ломая успешную операцию."""
        try:
            from store.tasks.audio import prepare_track_audio

            prepare_track_audio.delay(recording_id)
        except Exception:
            logger.exception(
                'Не удалось поставить подготовку аудио в очередь '
                'для записи %s.',
                recording_id,
            )
