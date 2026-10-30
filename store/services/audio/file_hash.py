import hashlib

HASH_CHUNK_SIZE = 1024 * 1024


def iter_file_chunks(source_file):
    """Читает файл порциями фиксированного размера."""
    while chunk := source_file.read(HASH_CHUNK_SIZE):
        yield chunk


def calculate_file_hash(source_file) -> str:
    """Вычисляет SHA-256 открытого файла."""
    hasher = hashlib.sha256()

    for chunk in iter_file_chunks(source_file):
        hasher.update(chunk)

    return hasher.hexdigest()
