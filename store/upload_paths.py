"""Пути загрузки медиафайлов магазина."""

from common.upload_paths import build_unique_filename


def album_cover_upload_to(instance, filename: str) -> str:
    """Формирует путь для обложки альбома."""
    return f'albums/covers/{build_unique_filename(filename)}'


def track_audio_upload_to(instance, filename):
    """Формирует путь для оригинального аудиофайла трека."""
    return (
        f'albums/{instance.album_id}/tracks/original/'
        f'{build_unique_filename(filename)}'
    )


def merch_image_upload_to(instance, filename: str) -> str:
    """Формирует путь для изображения мерча."""
    return (
        f'merch/{instance.merch_id}/images/{build_unique_filename(filename)}'
    )


def album_archive_upload_to(instance, filename: str) -> str:
    """Формирует путь для архива альбома."""
    return (
        f'albums/{instance.album_id}/archives/'
        f'{build_unique_filename(filename)}'
    )
