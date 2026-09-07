from celery import shared_task

from store.models.album import AlbumArchive
from store.services.album_archive import AlbumArchiveService


@shared_task(queue='archives')
def build_album_archive(
    album_id: int,
    expected_hash: str,
) -> None:
    """Собирает архив, только если задача всё ещё актуальна."""
    archive = AlbumArchive.objects.filter(
        album_id=album_id,
    ).first()

    if archive is None:
        return

    # За время задержки альбом уже изменили ещё раз.
    if archive.pending_hash != expected_hash:
        return

    AlbumArchiveService.build(
        album_id=album_id,
        expected_hash=expected_hash,
    )
