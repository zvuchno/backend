from celery import shared_task

from store.services.album_archive import AlbumArchiveService


@shared_task(queue='archives')
def build_album_archive(album_id: int) -> None:
    """Задача на создание архива альбома."""
    AlbumArchiveService.build(album_id)
