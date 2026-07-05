from django.db import transaction

from store.models import Track


class TrackGeneratedAudioScheduler:
    """Ставит подготовку производных аудиофайлов в очередь."""

    @classmethod
    def schedule(cls, track: Track) -> bool:
        """Ставит обработку трека в очередь после фиксации транзакции."""
        if not track.pk or not track.audio_file:
            return False

        track_id = track.pk

        transaction.on_commit(
            lambda: cls._enqueue(track_id),
        )

        return True

    @staticmethod
    def _enqueue(track_id: int) -> None:
        """Отправляет задачу подготовки файлов в Celery."""
        from store.tasks.audio import prepare_track_audio

        prepare_track_audio.delay(track_id)
