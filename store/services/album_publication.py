from store.models import Album

PUBLICATION_ERROR = 'Нельзя опубликовать релиз без загруженных треков.'


def has_uploaded_track(album: Album) -> bool:
    """Проверяет наличие активного трека с загруженным аудиофайлом."""
    return (
        album.tracks
        .filter(
            audio_file__isnull=False,
            is_active=True,
        )
        .exclude(audio_file='')
        .exists()
    )


def unpublish_if_empty(album: Album) -> None:
    """Снимает релиз с публикации, если в нём нет доступных треков."""
    if album.is_published and not has_uploaded_track(album):
        album.is_published = False
        album.save(update_fields=('is_published',))
