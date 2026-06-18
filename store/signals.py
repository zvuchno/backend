"""Сигналы приложения store."""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from store.models import Album
from store.services.album_archive import AlbumArchiveScheduler


@receiver(
    post_save,
    sender=Album,
    dispatch_uid='store.schedule_album_archive_after_save',
)
def schedule_album_archive_after_save(
    sender,
    instance: Album,
    raw: bool,
    **kwargs,
) -> None:
    """Проверяет необходимость пересборки после сохранения альбома."""
    if raw:
        return

    album_id = instance.pk

    transaction.on_commit(
        lambda: AlbumArchiveScheduler.schedule_by_id(album_id),
    )
