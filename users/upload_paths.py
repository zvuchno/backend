"""Пути загрузки пользовательских медиафайлов."""

from common.upload_paths import build_unique_filename


def artist_cover_upload_to(instance, filename: str) -> str:
    """Формирует путь для обложки артиста."""
    return f'artists/covers/{build_unique_filename(filename)}'
