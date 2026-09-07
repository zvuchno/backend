"""Постановка задач подготовки аудио после commit."""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)


class TrackGeneratedAudioScheduler:
    """Ставит подготовку производных аудиофайлов в очередь."""

    @classmethod
    def schedule(cls, track) -> None:
        """Ставит обработку трека в очередь после фиксации транзакции."""
        track_id = track.pk

        transaction.on_commit(
            lambda: cls._enqueue_safely(track_id),
        )

    @staticmethod
    def _enqueue_safely(track_id: int) -> None:
        """Ставит задачу в очередь, не ломая успешный upload."""
        try:
            from store.tasks.audio import prepare_track_audio

            prepare_track_audio.delay(track_id)
        except Exception:
            logger.exception(
                'Не удалось поставить подготовку аудио в очередь '
                'для трека %s.',
                track_id,
            )
