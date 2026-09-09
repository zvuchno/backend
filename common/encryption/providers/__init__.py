"""Источники keyring."""

from functools import lru_cache

from .selector import load_keyring


@lru_cache(maxsize=1)
def get_keyring():
    """Возвращает keyring текущего процесса."""
    return load_keyring()


def clear_keyring_cache() -> None:
    """Очищает кеш keyring."""
    get_keyring.cache_clear()


__all__ = [
    'clear_keyring_cache',
    'get_keyring',
]
