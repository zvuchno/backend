"""Пути загрузки медиафайлов магазина."""

from uuid import uuid4

from common.upload_paths import build_unique_filename


def album_cover_upload_to(instance, filename: str) -> str:
    """Формирует путь для обложки альбома."""
    return f'albums/covers/{build_unique_filename(filename)}'


def track_audio_upload_to(instance, filename):
    """Формирует путь для оригинального аудиофайла записи."""
    return f'recordings/original/{build_unique_filename(filename)}'


def bonus_upload_to(instance, filename):
    """Формирует путь для загрузки бонуса."""
    return (
        f'albums/{instance.album_id}/bonuses/{build_unique_filename(filename)}'
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


def track_preview_upload_to(instance, filename: str) -> str:
    """Формирует путь для публичного превью записи."""
    return f'recordings/preview/{build_unique_filename(filename)}'


def track_stream_upload_to(instance, filename: str) -> str:
    """Формирует путь для приватного файла воспроизведения записи."""
    return f'recordings/stream/{build_unique_filename(filename)}'


def track_upload_staging_key(
    recording_id: int,
    filename: str,
) -> str:
    """Формирует ключ временного объекта загрузки записи."""
    return (
        f'staging/track-uploads/{recording_id}/'
        f'{uuid4().hex}/'
        f'{build_unique_filename(filename)}'
    )
