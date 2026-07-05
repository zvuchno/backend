"""Общие функции формирования имён загружаемых файлов."""

from pathlib import Path
from uuid import uuid4


def build_unique_filename(filename: str) -> str:
    """Возвращает уникальное имя с расширением исходного файла."""
    suffix = Path(filename).suffix.lower()
    return f'{uuid4().hex}{suffix}'
